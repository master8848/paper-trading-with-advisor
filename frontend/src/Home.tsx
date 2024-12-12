import { useQuery } from "@tanstack/react-query";
import { BsGear } from "react-icons/bs";
import axios from "axios";
import React, { useState } from "react";
import Loader from "./Loader";
import Table from "./Table";
import TableConFigure from "./TableConfigurations";
type Tduration = "tweek" | "lWeek" | "tyear" | "lyear" | "tmonth" | "lmonth";

export default function Home() {
  const [Duration, setDuration] = useState<Tduration>("tweek");
  const [AllDatas, setAllDatas] = useState(false);
  const [message, setMessage] = useState("");
  const [OpenOptions, setOpenOptions] = useState(false);

  const { data, isLoading } = useQuery({
    queryFn: () =>
      axios.get(
        "http://localhost:3000/stocks?duration=" +
          Duration +
          (AllDatas ? "&load=true" : "")
      ),
    queryKey: ["Stocks", Duration, AllDatas],
    cacheTime: Infinity,
    staleTime: Infinity,
    retry(failureCount, error) {
      if (failureCount > 1) return false;
      return true;
    },
    refetchOnWindowFocus: false,
  });
  const {} = useQuery({
    queryFn: () => axios.get("http://localhost:3000/stock-exchange/Nse"),
    queryKey: ["NseStockName"],
    cacheTime: Infinity,
    refetchOnWindowFocus: false,
  });
  if (isLoading) return <Loader />;
  return (
    <div className="lg:flex">
      <div className="lg:hidden ">
        {message && <div className="mt-5">{message}</div>}
      </div>
      <div className="lg:max-w-5xl max-w-3xl lg:pl-20  my-8 pb-10 ">
        <div className="mt-1 sm:mt-0 sm:col-span-2 flex justify-between">
          <select
            value={Duration}
            onChange={(e) => {
              setDuration(e.target.value as Tduration);
            }}
            className="max-w-lg block focus:ring-indigo-500 focus:border-indigo-500 w-full shadow-sm sm:max-w-xs sm:text-sm border-gray-300 rounded-md"
          >
            {(
              [
                { key: "tweek", name: "This Week" },
                { key: "lWeek", name: "Last Week" },
                { key: "tyear", name: "This year" },
                { key: "lyear", name: "Last year" },
                { key: "tmonth", name: "This month" },
                { key: "lmonth", name: "Last month" },
              ] as const
            ).map((duration) => (
              <option key={duration.name} value={duration.key}>
                Show {duration.name}
              </option>
            ))}
          </select>
          <div className="flex ">
            <select
              value={AllDatas ? "true" : ""}
              onChange={(e) => {
                setAllDatas(!!e.target.value);
              }}
              className="max-w-lg block focus:ring-indigo-500 focus:border-indigo-500 w-full shadow-sm sm:max-w-xs sm:text-sm border-gray-300 rounded-md"
            >
              {(
                [
                  { key: "", name: "Less Time" },
                  { key: "true", name: "More Time" },
                ] as const
              ).map((duration) => (
                <option key={duration.name} value={duration.key}>
                  Show {duration.name}
                </option>
              ))}
            </select>
            <button className="ml-3" onClick={() => setOpenOptions(true)}>
              <BsGear size={30} />
            </button>
          </div>
        </div>
        <Table
          data={data?.data || []}
          queryKey={["Stocks", Duration, AllDatas]}
          setMessage={setMessage}
          longLoadedBool={AllDatas}
        />
      </div>
      <div className="hidden lg:block relative ">
        {message && <div className="mt-5 fixed pl-5">{message}</div>}
      </div>
      <TableConFigure open={OpenOptions} setOpen={setOpenOptions} />
    </div>
  );
}
