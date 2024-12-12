import React, { useEffect, useState } from "react";
import { AiOutlineArrowLeft, AiOutlineArrowRight } from "react-icons/ai";
import { MdOutlineEdit } from "react-icons/md";
import { RiDeleteBin5Fill } from "react-icons/ri";
import moment from "moment";
import {
  useTable,
  usePagination,
  useGlobalFilter,
  useAsyncDebounce,
  useFilters,
  useSortBy,
} from "react-table";
import AddEditStock from "./Form";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { useAppSelector } from "./store/app";
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
];

export default function Table({ data, queryKey, setMessage, longLoadedBool }) {
  const [addPannel, setAddPannel] = useState(false);
  const [editPannel, setEditPannel] = useState<any>(undefined);
  const queryClient = useQueryClient();
  const { longLoaded, shortLoaded } = useAppSelector((c) => c.configureTable);

  const mutation = useMutation({
    mutationFn: (id) => axios.delete("http://localhost:3000/stocks/" + id),
    onSuccess(data, id, context) {
      queryClient.setQueryData(queryKey, (oldData: any) => {
        if (oldData) {
          return {
            ...oldData,
            data: oldData?.data?.filter((data) => data.id != id),
          };
        }
        return oldData;
      });
    },
  });

  const columns = React.useMemo(
    () => [
      {
        Header: "ID",
        accessor: "id", // accessor is the "key" in the data
      },
      {
        Header: "Stock Name",
        accessor: "stockName", // accessor is the "key" in the data
      },
      {
        Header: "Price",
        accessor: "price",
      },
      {
        Header: "Modified At",
        accessor: "modified",
        Cell: ({ cell: { value } }) => moment(value).format("YYYY-MM-DD"),
      },
      {
        Header: "Created At",
        accessor: "date",
        Cell: ({ cell: { value } }) => moment(value).format("YYYY-MM-DD"),
      },
      {
        Header: "Messages",
        accessor: "message",
      },
      {
        Header: "LTP",
        accessor: "lastTradedPrice",
      },
      {
        Header: "52 week low",
        accessor: "fiftyTwoWeekLow",
      },
      {
        Header: "52 week high",
        accessor: "fiftyTwoWeekHigh",
      },
      {
        Header: "Total",
        accessor: "total",
      },
      {
        Header: "Type",
        accessor: "type",
      },
      {
        Header: "Quantity",
        accessor: "quantity",
      },
      {
        Header: "Action",
        accessor: "action",
        Cell: ({
          cell: {
            row: { values },
          },
        }) => (
          <div className="flex justify-center gap-5 w-10">
            <button
              onClick={() => {
                setEditPannel(values);
              }}
            >
              <MdOutlineEdit fill="blue" size={20} />
            </button>
            <button
              onClick={() => {
                console.log(values);
                // setEditPannel(values);
                mutation.mutate(values?.id);
              }}
              className="ml-5"
            >
              <RiDeleteBin5Fill fill="red" size={18} />
            </button>
          </div>
        ),
      },
    ],

    []
  );
  const defaultColumn = React.useMemo(
    () => ({
      // Let's set up our default Filter UI
      Filter: DefaultColumnFilter,
    }),
    []
  );

  const {
    getTableProps,
    getTableBodyProps,
    headerGroups,
    prepareRow,
    page,
    canPreviousPage,
    canNextPage,
    pageOptions,
    pageCount,
    gotoPage,
    nextPage,
    previousPage,
    visibleColumns,
    setGlobalFilter,
    setHiddenColumns,
    setPageSize,

    state: { pageIndex, pageSize },
  } = useTable(
    {
      columns,
      data,
      defaultColumn,
      initialState: {
        hiddenColumns: ["id", "message"],
      },
    },
    useFilters,
    useGlobalFilter,
    useSortBy,
    usePagination
  );
  useEffect(() => {
    setHiddenColumns([
      "id",
      "message",
      ...(longLoadedBool
        ? possibleColumns.filter((c) => !longLoaded.includes(c))
        : possibleColumns.filter((c) => !shortLoaded.includes(c))),
    ]);
  }, [longLoadedBool, longLoaded, shortLoaded]);

  return (
    <>
      <div className="flex justify-between my-8  ">
        <div className="flex gap-x-4">
          <GlobalFilter setGlobalFilter={setGlobalFilter} />
          <div className="mt-1 sm:mt-0 sm:col-span-2">
            <select
              value={pageSize}
              onChange={(e) => {
                setPageSize(Number(e.target.value));
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
            onClick={() => setAddPannel(true)}
            className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-indigo-700 bg-indigo-100 hover:bg-indigo-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
          >
            Add Item
          </button>
        </div>
      </div>
      <div className="flex flex-col ">
        <div className="-my-2 overflow-x-auto sm:-mx-6 lg:-mx-8">
          <div className="py-2 align-middle inline-block min-w-full sm:px-6 lg:px-8">
            <div className="shadow overflow-hidden border-b border-gray-200 sm:rounded-lg">
              <table
                className="min-w-full divide-y divide-gray-200"
                {...getTableProps()}
              >
                <thead className="bg-gray-50">
                  {headerGroups.map((headerGroup) => (
                    <tr {...headerGroup.getHeaderGroupProps()}>
                      {headerGroup.headers.map((column) => (
                        <th
                          {...column.getHeaderProps(
                            column.getSortByToggleProps()
                          )}
                          className="px-6 py-3 text-left w-fit text-xs font-medium text-gray-500 uppercase tracking-wider"
                          // {...column.getHeaderProps()}
                        >
                          {column.render("Header")}
                          <span>
                            {column.isSorted
                              ? column.isSortedDesc
                                ? " 🔽"
                                : " 🔼"
                              : ""}
                          </span>
                          <div>
                            {column.canFilter ? column.render("Filter") : null}
                          </div>
                        </th>
                      ))}
                    </tr>
                  ))}
                </thead>
                <tbody {...getTableBodyProps()}>
                  {page.map((row, index) => {
                    prepareRow(row);
                    return (
                      <tr
                        className={index % 2 === 0 ? "bg-white" : "bg-gray-50"}
                        {...row.getRowProps()}
                        onClick={() => setMessage(row?.values.message)}
                      >
                        {row.cells.map((cell) => {
                          return (
                            <td
                              className="px-6 py-4 max-w-[40px] truncate whitespace-nowrap text-sm text-gray-500"
                              {...cell.getCellProps()}
                            >
                              {cell.render("Cell")}
                            </td>
                          );
                        })}
                      </tr>
                    );
                  })}
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
            onClick={(ev) => {
              previousPage();
            }}
            className="border-t-2 border-transparent pt-4 pr-1 inline-flex items-center text-sm font-medium text-gray-500 hover:text-gray-700 hover:border-gray-300"
          >
            <AiOutlineArrowLeft className="mr-2" />
            Previous
          </button>
        </div>
        <div className="hidden md:-mt-px md:flex">
          {pageOptions.map((pagenumber) => (
            <button
              className={
                pagenumber != pageIndex
                  ? "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 border-t-2 pt-4 px-4 inline-flex items-center text-sm font-medium"
                  : "border-indigo-500 text-indigo-600 border-t-2 pt-4 px-4 inline-flex items-center text-sm font-medium"
              }
              onClick={() => gotoPage(pagenumber)}
              key={pagenumber}
            >
              {pagenumber < 0 || pagenumber < pageIndex - 5
                ? null
                : pagenumber > pageIndex + 5
                ? null
                : pagenumber + 1}
            </button>
          ))}
        </div>

        <div className="-mt-px w-0 flex-1 flex justify-end">
          <button
            disabled={!canNextPage}
            onClick={(ev) => {
              nextPage();
            }}
            className="border-t-2 border-transparent pt-4 pl-1 inline-flex items-center text-sm font-medium text-gray-500 hover:text-gray-700 hover:border-gray-300"
          >
            Next
            <AiOutlineArrowRight className="ml-2" />
          </button>
        </div>
      </nav>
      <AddEditStock
        toggle={() => setAddPannel(false)}
        isOpen={addPannel}
        queryKey={queryKey}
      />
      <AddEditStock
        toggle={() => setEditPannel(undefined)}
        isOpen={!!editPannel}
        edit={true}
        defaultValues={editPannel}
        queryKey={queryKey}
      />
    </>
  );
}

function GlobalFilter({ setGlobalFilter }) {
  const [value, setValue] = React.useState("");
  const onChange = useAsyncDebounce((value) => {
    setGlobalFilter(value || undefined);
  }, 200);

  return (
    <div>
      <label htmlFor="email" className="sr-only">
        Search
      </label>
      <input
        type="search"
        value={value || ""}
        onChange={(e) => {
          setValue(e.target.value);
          onChange(e.target.value);
        }}
        className="shadow-sm focus:ring-indigo-500 focus:border-indigo-500 block w-full sm:text-sm border-gray-300 rounded-md"
        placeholder="Search"
      />
    </div>
  );
}

function DefaultColumnFilter({ column: { filterValue, setFilter } }) {
  return (
    <div className="mt-2">
      <label htmlFor="email" className="sr-only">
        Search
      </label>
      <input
        type="search"
        value={filterValue || ""}
        onChange={(e) => {
          setFilter(e.target.value || undefined); // Set undefined to remove the filter entirely
        }}
        className="shadow-sm focus:ring-indigo-500 focus:border-indigo-500 block w-full sm:text-sm border-gray-300 rounded-md"
        placeholder="Search"
      />
    </div>
  );
}
