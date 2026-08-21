/**
 * PaperTradeTable — TanStack Table v9 ( @tanstack/react-table@^9 )
 *
 * Migrated from v8 `useReactTable` + `createColumnHelper<TData>` to v9
 * `useTable` + `tableFeatures` + `createColumnHelper<TFeatures, TData>`.
 *
 * Breaking change fixed:
 *   v8:  createColumnHelper<StockRow>()
 *   v9:  createColumnHelper<typeof features, StockRow>()
 *        (first generic is now TFeatures from tableFeatures())
 *
 * Other v9 notes:
 * - `useReactTable` → `useTable` (react adapter)
 * - Row models are now configured via `tableFeatures({ ... rowModels })`
 *   instead of `get*RowModel()` table options alone (legacy compat still
 *   available via `useLegacyTable` / `@tanstack/react-table/legacy`).
 * - Rendering via `table.FlexRender` (or `flexRender(header.column.columnDef.header, header.getContext())`).
 * - Column visibility controlled via `columnVisibility` state (replaces `setHiddenColumns`).
 * - No axios — fetch is used for mutations to avoid reintroducing the removed dep.
 */
import React, { useEffect, useMemo, useState } from "react";
import { AiOutlineArrowLeft, AiOutlineArrowRight } from "react-icons/ai";
import { MdOutlineEdit } from "react-icons/md";
import { RiDeleteBin5Fill } from "react-icons/ri";
import moment from "moment";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useAppSelector } from "../store/app";
import AddEditStock from "../Form";
import {
  columnFilteringFeature,
  columnVisibilityFeature,
  createColumnHelper,
  createFilteredRowModel,
  createPaginatedRowModel,
  createSortedRowModel,
  flexRender,
  globalFilteringFeature,
  rowPaginationFeature,
  rowSortingFeature,
  tableFeatures,
  useTable,
} from "@tanstack/react-table";
import type {
  ColumnVisibilityState,
  SortingState,
} from "@tanstack/react-table";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
export type StockRow = {
  id: string | number;
  stockName: string;
  price: number | string;
  date: string;
  modified: string;
  message?: string;
  lastTradedPrice?: number;
  fiftyTwoWeekLow?: number;
  fiftyTwoWeekHigh?: number;
  quantity?: number | string;
  type?: string;
  total?: number;
  [key: string]: unknown;
};

const possibleColumns = [
  "lastTradedPrice",
  "fiftyTwoWeekLow",
  "fiftyTwoWeekHigh",
  "price",
  "date",
  "modified",
  "type",
  "quantity",
  "total",
] as const;

// ---------------------------------------------------------------------------
// v9 feature set — stock trading UX needs sorting + filtering (global +
// column) + pagination + visibility. Empty `tableFeatures({})` would render a
// basic table only; we register the features we actually use so they are
// tree-shakable and typed.
// ---------------------------------------------------------------------------
const features = tableFeatures({
  columnFilteringFeature,
  columnVisibilityFeature,
  globalFilteringFeature,
  rowPaginationFeature,
  rowSortingFeature,
  filteredRowModel: createFilteredRowModel(),
  sortedRowModel: createSortedRowModel(),
  paginatedRowModel: createPaginatedRowModel(),
});

// v9 breaking change: first generic is TFeatures, second is TData.
// v8 was createColumnHelper<StockRow>() — now it is createColumnHelper<typeof features, StockRow>()
const columnHelper = createColumnHelper<typeof features, StockRow>();

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------
type Props = {
  data: StockRow[];
  queryKey: readonly unknown[];
  setMessage: (msg: string) => void;
  longLoadedBool: boolean;
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
export default function PaperTradeTable({
  data,
  queryKey,
  setMessage,
  longLoadedBool,
}: Props) {
  const [addPanel, setAddPanel] = useState(false);
  const [editPanel, setEditPanel] = useState<StockRow | undefined>(undefined);
  const queryClient = useQueryClient();
  const { longLoaded, shortLoaded } = useAppSelector((c) => c.configureTable);

  // Controlled table state
  const [sorting, setSorting] = useState<SortingState>([]);
  const [globalFilter, setGlobalFilter] = useState("");
  const [pagination, setPagination] = useState({ pageIndex: 0, pageSize: 10 });
  const [columnVisibility, setColumnVisibility] = useState<ColumnVisibilityState>({
    id: false,
    message: false,
  });

  // Sync hidden columns to longLoaded / shortLoaded (parity with legacy Table.tsx)
  useEffect(() => {
    const loaded = longLoadedBool ? longLoaded : shortLoaded;
    const hidden = (possibleColumns as readonly string[]).filter(
      (c) => !loaded.includes(c)
    );
    const next: ColumnVisibilityState = {
      id: false,
      message: false,
    };
    hidden.forEach((c) => {
      next[c] = false;
    });
    // visible columns are implied `true` when absent from the map, so we only
    // need to record `false` entries. Previously hidden columns that are now
    // visible are removed from the map → become visible.
    setColumnVisibility(next);
  }, [longLoaded, shortLoaded, longLoadedBool]);

  // Delete via fetch (do not reintroduce axios)
  const mutation = useMutation({
    mutationFn: async (id: string | number) => {
      const res = await fetch(`http://localhost:3000/stocks/${id}`, {
        method: "DELETE",
      });
      if (!res.ok) throw new Error(`Delete failed: ${res.status}`);
      // backend may return empty body
      const text = await res.text();
      try {
        return text ? JSON.parse(text) : {};
      } catch {
        return {};
      }
    },
    onSuccess(_data, id) {
      queryClient.setQueryData(queryKey as unknown as string[], (oldData: any) => {
        if (oldData) {
          return {
            ...oldData,
            data: oldData?.data?.filter((d: StockRow) => String(d.id) !== String(id)),
          };
        }
        return oldData;
      });
    },
  });

  const columns = useMemo(
    () =>
      columnHelper.columns([
        columnHelper.accessor("id", {
          header: "ID",
          enableHiding: true,
        }),
        columnHelper.accessor("stockName", {
          header: "Stock Name",
        }),
        columnHelper.accessor("price", {
          header: "Price",
        }),
        columnHelper.accessor("modified", {
          header: "Modified At",
          cell: (info) => {
            const v = info.getValue() as string;
            return v ? moment(v).format("YYYY-MM-DD") : "";
          },
        }),
        columnHelper.accessor("date", {
          header: "Created At",
          cell: (info) => {
            const v = info.getValue() as string;
            return v ? moment(v).format("YYYY-MM-DD") : "";
          },
        }),
        columnHelper.accessor("message", {
          header: "Messages",
          enableHiding: true,
        }),
        columnHelper.accessor("lastTradedPrice", {
          header: "LTP",
        }),
        columnHelper.accessor("fiftyTwoWeekLow", {
          header: "52 week low",
        }),
        columnHelper.accessor("fiftyTwoWeekHigh", {
          header: "52 week high",
        }),
        columnHelper.accessor("total", {
          header: "Total",
        }),
        columnHelper.accessor("type", {
          header: "Type",
        }),
        columnHelper.accessor("quantity", {
          header: "Quantity",
        }),
        columnHelper.display({
          id: "action",
          header: "Action",
          cell: ({ row }) => {
            const values = row.original;
            return (
              <div className="flex justify-center gap-5 w-10">
                <button onClick={() => setEditPanel(values)}>
                  <MdOutlineEdit fill="blue" size={20} />
                </button>
                <button
                  onClick={() => mutation.mutate(values.id)}
                  className="ml-5"
                >
                  <RiDeleteBin5Fill fill="red" size={18} />
                </button>
              </div>
            );
          },
        }),
      ]),
    // mutation is stable; setEditPanel is setter — no need to recreate columns
    []
  );

  const table = useTable(
    {
      features,
      columns,
      data,
      state: {
        sorting,
        globalFilter,
        pagination,
        columnVisibility,
      },
      onSortingChange: setSorting,
      onGlobalFilterChange: setGlobalFilter,
      onPaginationChange: setPagination,
      onColumnVisibilityChange: setColumnVisibility,
      getRowId: (row) => String((row as StockRow).id),
      debugTable: false,
    },
    (state) => state
  );

  const pageCount = table.getPageCount();
  const canPreviousPage = table.getCanPreviousPage();
  const canNextPage = table.getCanNextPage();

  return (
    <>
      <div className="flex justify-between my-8">
        <div className="flex gap-x-4">
          <input
            type="search"
            value={globalFilter ?? ""}
            onChange={(e) => setGlobalFilter(e.target.value)}
            className="shadow-sm focus:ring-indigo-500 focus:border-indigo-500 block w-full sm:text-sm border-gray-300 rounded-md"
            placeholder="Search"
          />
          <div className="mt-1 sm:mt-0 sm:col-span-2">
            <select
              value={pagination.pageSize}
              onChange={(e) => {
                table.setPageSize(Number(e.target.value));
              }}
              className="max-w-lg block focus:ring-indigo-500 focus:border-indigo-500 w-full shadow-sm sm:max-w-xs sm:text-sm border-gray-300 rounded-md"
            >
              {[10, 20, 30, 40, 50].map((pageSize) => (
                <option key={pageSize} value={pageSize}>
                  Show {pageSize}
                </option>
              ))}
            </select>
          </div>
        </div>
        <div>
          <button
            type="button"
            onClick={() => setAddPanel(true)}
            className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-indigo-700 bg-indigo-100 hover:bg-indigo-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
          >
            Add Item
          </button>
        </div>
      </div>

      <div className="flex flex-col">
        <div className="-my-2 overflow-x-auto sm:-mx-6 lg:-mx-8">
          <div className="py-2 align-middle inline-block min-w-full sm:px-6 lg:px-8">
            <div className="shadow overflow-hidden border-b border-gray-200 sm:rounded-lg">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  {table.getHeaderGroups().map((headerGroup) => (
                    <tr key={headerGroup.id}>
                      {headerGroup.headers.map((header) => (
                        <th
                          key={header.id}
                          colSpan={header.colSpan}
                          className="px-6 py-3 text-left w-fit text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer select-none"
                          onClick={header.column.getToggleSortingHandler()}
                        >
                          {header.isPlaceholder ? null : (
                            <>
                              {flexRender(
                                header.column.columnDef.header,
                                header.getContext()
                              )}
                              {{
                                asc: " 🔼",
                                desc: " 🔽",
                              }[header.column.getIsSorted() as string] ?? null}
                              {header.column.getCanFilter() ? (
                                <div
                                  onClick={(e) => e.stopPropagation()}
                                  className="mt-2"
                                >
                                  <input
                                    type="search"
                                    value={
                                      (header.column.getFilterValue() as string) ?? ""
                                    }
                                    onChange={(e) =>
                                      header.column.setFilterValue(
                                        e.target.value || undefined
                                      )
                                    }
                                    className="shadow-sm focus:ring-indigo-500 focus:border-indigo-500 block w-full sm:text-sm border-gray-300 rounded-md font-normal normal-case"
                                    placeholder="Search"
                                  />
                                </div>
                              ) : null}
                            </>
                          )}
                        </th>
                      ))}
                    </tr>
                  ))}
                </thead>
                <tbody>
                  {table.getRowModel().rows.map((row, index) => (
                    <tr
                      key={row.id}
                      className={index % 2 === 0 ? "bg-white" : "bg-gray-50"}
                      onClick={() =>
                        setMessage((row.original.message as string) || "")
                      }
                    >
                      {row.getVisibleCells().map((cell) => (
                        <td
                          key={cell.id}
                          className="px-6 py-4 max-w-[40px] truncate whitespace-nowrap text-sm text-gray-500"
                        >
                          {flexRender(
                            cell.column.columnDef.cell,
                            cell.getContext()
                          )}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>

      <nav className="border-t border-gray-200 px-4 flex items-center justify-between sm:px-0">
        <div className="-mt-px w-0 flex-1 flex">
          <button
            disabled={!canPreviousPage}
            onClick={() => table.previousPage()}
            className="border-t-2 border-transparent pt-4 pr-1 inline-flex items-center text-sm font-medium text-gray-500 hover:text-gray-700 hover:border-gray-300 disabled:opacity-50"
          >
            <AiOutlineArrowLeft className="mr-2" />
            Previous
          </button>
        </div>
        <div className="hidden md:-mt-px md:flex">
          {Array.from({ length: pageCount }, (_, i) => i).map((pagenumber) => (
            <button
              key={pagenumber}
              className={
                pagenumber !== pagination.pageIndex
                  ? "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 border-t-2 pt-4 px-4 inline-flex items-center text-sm font-medium"
                  : "border-indigo-500 text-indigo-600 border-t-2 pt-4 px-4 inline-flex items-center text-sm font-medium"
              }
              onClick={() => table.setPageIndex(pagenumber)}
            >
              {pagenumber < 0 || pagenumber < pagination.pageIndex - 5
                ? null
                : pagenumber > pagination.pageIndex + 5
                ? null
                : pagenumber + 1}
            </button>
          ))}
        </div>
        <div className="-mt-px w-0 flex-1 flex justify-end">
          <button
            disabled={!canNextPage}
            onClick={() => table.nextPage()}
            className="border-t-2 border-transparent pt-4 pl-1 inline-flex items-center text-sm font-medium text-gray-500 hover:text-gray-700 hover:border-gray-300 disabled:opacity-50"
          >
            Next
            <AiOutlineArrowRight className="ml-2" />
          </button>
        </div>
      </nav>

      <AddEditStock
        toggle={() => setAddPanel(false)}
        isOpen={addPanel}
        queryKey={queryKey as unknown as string[]}
      />
      <AddEditStock
        toggle={() => setEditPanel(undefined)}
        isOpen={!!editPanel}
        edit={true}
        defaultValues={editPanel as any}
        queryKey={queryKey as unknown as string[]}
      />
    </>
  );
}
