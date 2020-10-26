import json
from collections import defaultdict
from typing import Any
from typing import cast
from typing import DefaultDict
from typing import Dict
from typing import List
from typing import Optional
from typing import Set
from typing import Tuple

import apsw
from shillelagh.adapters.base import Adapter
from shillelagh.fields import Field
from shillelagh.fields import Order
from shillelagh.filters import Filter
from shillelagh.types import Constraint
from shillelagh.types import Index


class VTModule:
    def __init__(self, adapter: Adapter):
        self.adapter = adapter

    def Create(
        self,
        connection: apsw.Connection,
        modulename: str,
        dbname: str,
        tablename: str,
        *args: str,
    ) -> Tuple[str, "VTTable"]:
        adapter = self.adapter(*args)
        table = VTTable(adapter)
        create_table: str = table.get_create_table(tablename)
        return create_table, table

    Connect = Create


class VTTable:
    def __init__(self, adapter: Adapter):
        self.adapter = adapter

    def get_create_table(self, tablename: str) -> str:
        columns = self.adapter.get_columns()
        formatted_columns = ", ".join(f'"{k}" {v.type}' for (k, v) in columns.items())
        return f'CREATE TABLE "{tablename}" ({formatted_columns})'

    def BestIndex(
        self, constraints: List[Tuple[int, int]], orderbys: List[Tuple[int, bool]],
    ) -> Tuple[List[Constraint], int, str, bool, int]:
        column_types = list(self.adapter.get_columns().values())

        index_number = 42
        estimated_cost = 666

        indexes: List[Index] = []
        constraints_used: List[Constraint] = []
        filter_index = 0
        for column_index, operator in constraints:
            column_type = column_types[column_index]
            for class_ in column_type.filters:
                if operator in class_.operators:
                    constraints_used.append((filter_index, column_type.exact))
                    filter_index += 1
                    indexes.append((column_index, operator))
                    break
            else:
                # no indexes supported in this column
                constraints_used.append(None)

        # serialize the indexes to str so it can be used later when filtering the data
        index_name = json.dumps(indexes)

        # is the data being returned in the requested order? if not, SQLite will have
        # to sort it
        orderby_consumed = True
        for column_index, descending in orderbys:
            requested_order = Order.DESCENDING if descending else Order.ASCENDING
            column_type = column_types[column_index]
            if column_type.order != requested_order:
                orderby_consumed = False
                break

        return (
            constraints_used,
            index_number,
            index_name,
            orderby_consumed,
            estimated_cost,
        )

    def Open(self) -> "VTCursor":
        return VTCursor(self.adapter)

    def Disconnect(self) -> None:
        self.adapter.close()

    Destroy = Disconnect

    def UpdateInsertRow(self, rowid: Optional[int], fields: Tuple[Any, ...]) -> int:
        column_names = ["rowid"] + list(self.adapter.get_columns().keys())
        row = dict(zip(column_names, [rowid] + list(fields)))
        return self.adapter.insert_row(row)

    def UpdateDeleteRow(self, rowid: int) -> None:
        self.adapter.delete_row(rowid)

    def UpdateChangeRow(
        self, rowid: int, newrowid: int, fields: Tuple[Any, ...],
    ) -> None:
        column_names = ["rowid"] + list(self.adapter.get_columns().keys())
        row = dict(zip(column_names, [newrowid] + list(fields)))
        self.adapter.update_row(rowid, row)


class VTCursor:
    def __init__(self, adapter: Adapter):
        self.adapter = adapter

    def Filter(
        self, indexnumber: int, indexname: str, constraintargs: List[Any],
    ) -> None:
        columns: Dict[str, Field] = self.adapter.get_columns()
        column_names: List[str] = list(columns.keys())
        indexes: List[Index] = json.loads(indexname)

        all_bounds: DefaultDict[str, Set[Tuple[int, Any]]] = defaultdict(set)
        for (column_index, operator), constraint in zip(indexes, constraintargs):
            column_name = column_names[column_index]
            column_type = columns[column_name]
            value = column_type.parse(constraint)
            all_bounds[column_name].add((operator, value))

        # find the filter that works with all the operations and build it
        bounds: Dict[str, Filter] = {}
        for column_name, operations in all_bounds.items():
            column_type = columns[column_name]
            operators = {operation[0] for operation in operations}
            for class_ in column_type.filters:
                if all(operator in class_.operators for operator in operators):
                    break
            else:
                raise Exception("No valid filter found")
            bounds[column_name] = class_.build(operations)

        self.data = (
            tuple(row[name] for name in ["rowid"] + column_names)
            for row in self.adapter.get_data(bounds)
        )
        self.Next()

    def Eof(self) -> bool:
        return self.eof

    def Rowid(self) -> int:
        return cast(int, self.current_row[0])

    def Column(self, col) -> Any:
        return self.current_row[1 + col]

    def Next(self) -> None:
        try:
            self.current_row = next(self.data)
            self.eof = False
        except StopIteration:
            self.eof = True

    def Close(self) -> None:
        pass