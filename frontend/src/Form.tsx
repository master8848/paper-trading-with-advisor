import React, { Fragment, useEffect, useState } from "react";
import Select from "react-select";
import { Dialog, Switch, Transition } from "@headlessui/react";
import { useForm } from "react-hook-form";
import axios from "axios";
import { toast } from "react-toastify";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
// import { NseIndia } from "stock-nse-india";
// import Creatable from "react-select/creatable";
import CreatableSelect from "react-select/creatable";

export default function AddEditStock({
  edit = false,
  id = 0,
  toggle,
  isOpen,
  defaultValues = { stockName: "", price: 0, message: "" },
  queryKey,
}) {
  return (
    <>
      <main className="lg:min-h-full lg:overflow-hidden lg:flex lg:flex-row-reverse">
        <Transition appear show={isOpen} as={Fragment}>
          <Dialog as="div" className="relative z-10" onClose={toggle}>
            <Transition.Child
              as={Fragment}
              enter="ease-out duration-300"
              enterFrom="opacity-0"
              enterTo="opacity-100"
              leave="ease-in duration-200"
              leaveFrom="opacity-100"
              leaveTo="opacity-0"
            >
              <div className="fixed inset-0 bg-black bg-opacity-25" />
            </Transition.Child>
            {isOpen && (
              <div className="fixed inset-0 overflow-y-auto">
                <div className="flex min-h-full items-center justify-center p-4 text-center">
                  <Transition.Child
                    as={Fragment}
                    enter="ease-out duration-300"
                    enterFrom="opacity-0 scale-95"
                    enterTo="opacity-100 scale-100"
                    leave="ease-in duration-200"
                    leaveFrom="opacity-100 scale-100"
                    leaveTo="opacity-0 scale-95"
                  >
                    <Dialog.Panel className="w-full max-w-xl transform overflow-hidden rounded-2xl bg-white p-6 text-left align-middle shadow-xl transition-all">
                      <Dialog.Title
                        as="h3"
                        className="text-lg font-medium leading-6 text-gray-900"
                      >
                        {edit ? "Edit Item" : "Add Item"}
                      </Dialog.Title>

                      <FormSmall
                        edit={edit}
                        id={id}
                        toggle={toggle}
                        defaultValues={defaultValues}
                        queryKey={queryKey}
                      />
                    </Dialog.Panel>
                  </Transition.Child>
                </div>
              </div>
            )}
          </Dialog>
        </Transition>
      </main>
    </>
  );
}

function FormSmall({
  edit = false,
  id = 0,
  defaultValues = {
    stockName: "",
    price: 0,
    message: "",
    quantity: "1",
    type: "buy",
  },
  toggle,
  queryKey,
}) {
  const [Symbole, setSymbole] = useState("");
  const { data: optionsNse, isLoading } = useQuery({
    queryFn: () => axios.get("http://localhost:3000/stock-exchange/Nse"),
    queryKey: ["NseStockName"],
    cacheTime: Infinity,
    refetchOnMount: false,
    refetchOnWindowFocus: false,
    select: (d) => d.data?.map((c) => ({ value: c, label: c })) || [],
  });

  const { register, reset, handleSubmit } = useForm({
    defaultValues,
  });
  const { data: Prices } = useQuery({
    queryFn: () => axios.get("http://localhost:3000/stock-exchange/" + Symbole),
    queryKey: ["NSE_LasT_TradedPrice", Symbole],
    cacheTime: Infinity,
    refetchOnMount: false,
    enabled: !!Symbole,
    refetchOnWindowFocus: false,
    select: (d) => d?.data || {},
  });
  useEffect(() => {
    reset({ price: Prices?.lastTradedPrice });
  }, [Prices]);

  const queryClient = useQueryClient();
  const mutation = useMutation({
    mutationFn: ({ id, data }: any) =>
      edit
        ? axios.patch("http://localhost:3000/stocks/" + id, {
            ...data,
            stockName: Symbole,
            username: "MBSKS",
          })
        : axios.post("http://localhost:3000/stocks", {
            ...data,
            stockName: Symbole,
            username: "MBSKS",
          }),
    onError(error) {
      toast.error(
        "Error while " + (edit ? "editing" : "adding") + " your stock"
      );
      console.error(error);
    },
    onSuccess(data, id, context) {
      queryClient.setQueryData(queryKey, (oldData: any) => {
        toast.success(
          "Item was " + (edit ? "edited" : "added") + " successfully"
        );
        if (oldData) {
          return {
            ...oldData,
            data: edit
              ? [...oldData?.data?.filter((data) => data.id != id), data.data]
              : [...oldData?.data, data.data],
          };
        }
        return oldData;
      });
      toggle();
    },
  });
  const onSubmit = async (data) => {
    console.log(data);
    mutation.mutate({ id, data });
  };

  return (
    <section
      aria-labelledby="payment-heading"
      className="flex-auto overflow-y-auto px-1 pt-5 pb-9 sm:px-3  "
    >
      <div className="max-w-lg mx-auto lg:pt-5">
        <form className="" onSubmit={handleSubmit(onSubmit)}>
          {edit && <h1 className="text-lg">{defaultValues?.stockName}</h1>}
          <div className="mb-2">
            <select
              {...register("type")}
              className=" block focus:ring-indigo-500 focus:border-indigo-500 shadow-sm w-full sm:text-sm border-gray-300 rounded-md"
            >
              {(
                [
                  { key: "buy", name: "Buy" },
                  { key: "sell", name: "Sell" },
                ] as const
              ).map((duration) => (
                <option key={duration.name} value={duration.key}>
                  {duration.name}
                </option>
              ))}
            </select>
          </div>
          <div className="grid gap-y-4">
            {edit || (
              <div>
                <label
                  htmlFor="name-on-card"
                  className="block text-sm font-medium text-gray-700"
                >
                  Name of Stock
                </label>
                <div className="mt-1">
                  <CreatableSelect
                    isSearchable
                    options={optionsNse}
                    onChange={({ value }) => {
                      if (!value) return;
                      // reset((c) => ({ ...c, stockName: value as any }));
                      setSymbole(value);
                    }}
                  />
                </div>
              </div>
            )}
            {edit ? (
              <h1 className="text-lg">{defaultValues?.quantity}</h1>
            ) : (
              <div>
                <label
                  htmlFor="name-on-card"
                  className="block text-sm font-medium text-gray-700"
                >
                  Quantity
                </label>
                <div className="mt-1">
                  <input
                    type="number"
                    {...register("quantity")}
                    className="focus:ring-indigo-500 focus:border-indigo-500 block w-full pl-7 lg:pr-12  sm:text-sm border-gray-300 rounded-md"
                    placeholder="0"
                  />
                </div>
              </div>
            )}
            <div>
              <label
                htmlFor="price"
                className="block text-sm font-medium text-gray-700"
              >
                Price
              </label>
              <div className="mt-1 relative rounded-md shadow-sm">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <span className="text-gray-500 sm:text-sm">₹</span>
                </div>
                <input
                  type="number"
                  //   name="price"
                  //   id="price"
                  {...register("price")}
                  step={0.01}
                  className="focus:ring-indigo-500 focus:border-indigo-500 block w-full pl-7 lg:pr-12  sm:text-sm border-gray-300 rounded-md"
                  placeholder="0.00"
                  // aria-describedby="price-currency"
                />
                <div className="absolute inset-y-0 right-0 pr-3 lg:flex items-center pointer-events-none hidden ">
                  <span
                    className="text-gray-500 sm:text-sm"
                    id="price-currency"
                  >
                    Rupee
                  </span>
                </div>
              </div>
            </div>
            <div>
              <label
                htmlFor="comment"
                className="block text-sm font-medium text-gray-700"
              >
                Add your comment
              </label>
              <div className="mt-1">
                <textarea
                  rows={4}
                  //   name="comment"
                  //   id="comment"
                  className="shadow-sm max-h-96 min-h-[60px] focus:ring-indigo-500 focus:border-indigo-500 block w-full sm:text-sm border-gray-300 rounded-md"
                  {...register("message")}
                  //   defaultValue={""}
                />
              </div>
            </div>
          </div>
          <button
            type="submit"
            className="w-full mt-6 bg-indigo-600 border border-transparent rounded-md shadow-sm py-2 px-4 text-sm font-medium text-white hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
          >
            {edit ? "Edit" : "Add"}Stock
          </button>
          <button
            onClick={() => reset()}
            className="w-full mt-6 bg-indigo-600 border border-transparent rounded-md shadow-sm py-2 px-4 text-sm font-medium text-white hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
          >
            Reset Form Data
          </button>
        </form>
      </div>
      {Symbole && (
        <div className="flex justify-between">
          <div className="">
            LTP {"=>"}
            {Prices?.lastTradedPrice}
          </div>
          <div className="">
            52WL {"=>"}
            {Prices?.fiftyTwoWeekLow}
          </div>
          <div className="">
            52WH {"=>"}
            {Prices?.fiftyTwoWeekHigh}
          </div>
        </div>
      )}
    </section>
  );
}
