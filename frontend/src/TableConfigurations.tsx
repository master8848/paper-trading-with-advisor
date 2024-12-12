import { HiXMark, HiChevronUpDown } from "react-icons/hi2";
import { BsCheckLg } from "react-icons/bs";
import React, { Fragment, useEffect, useState } from "react";
import { Dialog, Transition, Listbox } from "@headlessui/react";
import { useAppDispatch, useAppSelector } from "./store/app";
import { setLongLoaded, setShortLoaded } from "./store/configureSettingsSlice";
// import { CheckIcon, ChevronUpDownIcon } from '@heroicons/react/20/solid'

const LongLoadingConfigure = [
  { name: "lastTradedPrice", label: "LTP" },
  { name: "fiftyTwoWeekLow", label: "52W High" },
  { name: "fiftyTwoWeekHigh", label: "52W Low" },
  { name: "price", label: "Price" },
  { name: "date", label: "Creation Date" },
  { name: "modified", label: "Modified Date" },
  { name: "type", label: "Type of Transaction" },
  { name: "quantity", label: "Quantity Traded" },
  { name: "total", label: "Total ammount" },
];
const ShortLoadingConfigure = [
  { name: "price", label: "Price" },
  { name: "date", label: "Creation Date" },
  { name: "modified", label: "Modified Date" },
  { name: "type", label: "Type of Transaction" },
  { name: "quantity", label: "Quantity Traded" },
  { name: "total", label: "Total ammount" },
];

export default function TableConFigure({ open, setOpen }) {
  const { longLoaded, shortLoaded } = useAppSelector((c) => c.configureTable);
  const dispatch = useAppDispatch();
  const [selectedLong, setSelectedLong] = useState<
    {
      name: string;
      label: string;
    }[]
  >([]);
  const [selectedShort, setSelectedShort] = useState<
    {
      name: string;
      label: string;
    }[]
  >([]);
  useEffect(() => {
    setSelectedLong(
      LongLoadingConfigure.filter((c) => longLoaded.includes(c.name))
    );
    setSelectedShort(
      ShortLoadingConfigure.filter((c) => shortLoaded.includes(c.name))
    );
  }, [longLoaded, shortLoaded]);
  const handleSubmit = (ev) => {
    ev.preventDefault();
    dispatch(setLongLoaded(selectedLong.map((c) => c.name)));
    dispatch(setShortLoaded(selectedShort.map((c) => c.name)));
  };
  return (
    <Transition.Root show={open} as={Fragment}>
      <Dialog
        as="div"
        className="fixed inset-0 overflow-hidden"
        onClose={setOpen}
      >
        <div className="absolute inset-0 overflow-hidden">
          <Dialog.Overlay className="absolute inset-0" />

          <form
            onSubmit={handleSubmit}
            className="fixed inset-y-0 right-0 pl-10 max-w-full flex"
          >
            <Transition.Child
              as={Fragment}
              enter="transform transition ease-in-out duration-500 sm:duration-700"
              enterFrom="translate-x-full"
              enterTo="translate-x-0"
              leave="transform transition ease-in-out duration-500 sm:duration-700"
              leaveFrom="translate-x-0"
              leaveTo="translate-x-full"
            >
              <div className="w-screen max-w-md">
                <div className="h-full flex flex-col bg-white shadow-xl overflow-y-scroll">
                  <div className="py-6 px-4 bg-indigo-700 sm:px-6">
                    <div className="flex items-center justify-between">
                      <Dialog.Title className="text-lg font-medium text-white">
                        Table Settings
                      </Dialog.Title>
                      <div className="ml-3 h-7 flex items-center">
                        <button
                          type="button"
                          className="bg-indigo-700 rounded-md text-indigo-200 hover:text-white focus:outline-none focus:ring-2 focus:ring-white"
                          onClick={() => setOpen(false)}
                        >
                          <span className="sr-only">Close panel</span>
                          <HiXMark size={30} />
                          {/* <XIcon className="h-6 w-6" aria-hidden="true" /> */}
                        </button>
                      </div>
                    </div>
                  </div>
                  <div className="relative flex-1 py-6 px-4 sm:px-6">
                    {/* Replace with your content */}
                    <div className="absolute inset-0 py-6 px-4 sm:px-6">
                      <div className="mb-8">
                        If you selected long loaging
                        <Listbox
                          multiple
                          value={selectedLong}
                          onChange={setSelectedLong}
                        >
                          <div className="relative mt-1">
                            <Listbox.Button className="relative w-full cursor-default rounded-lg bg-white py-2 pl-3 pr-10 text-left shadow-md focus:outline-none focus-visible:border-indigo-500 focus-visible:ring-2 focus-visible:ring-white focus-visible:ring-opacity-75 focus-visible:ring-offset-2 focus-visible:ring-offset-orange-300 sm:text-sm">
                              <span className="block truncate">
                                {selectedLong
                                  .map((person) => person.name)
                                  .join(", ") || "Please select a item"}
                              </span>
                              <span className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-2">
                                <HiChevronUpDown
                                  className="h-5 w-5 text-gray-400"
                                  aria-hidden="true"
                                />
                              </span>
                            </Listbox.Button>
                            <Transition
                              as={Fragment}
                              leave="transition ease-in duration-100"
                              leaveFrom="opacity-100"
                              leaveTo="opacity-0"
                            >
                              <Listbox.Options className="absolute mt-1 z-10 max-h-60 w-full overflow-auto rounded-md bg-white py-1 text-base shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none sm:text-sm">
                                {LongLoadingConfigure.map(
                                  (person, personIdx) => (
                                    <Listbox.Option
                                      key={personIdx}
                                      className={({ active }) =>
                                        `relative cursor-default select-none py-2 pl-10 pr-4 ${
                                          active
                                            ? "bg-amber-100 text-amber-900"
                                            : "text-gray-900"
                                        }`
                                      }
                                      value={person}
                                    >
                                      {({ selected }) => (
                                        <>
                                          <span
                                            className={`block truncate ${
                                              selected
                                                ? "font-medium"
                                                : "font-normal"
                                            }`}
                                          >
                                            {person.name}
                                          </span>
                                          {selected ? (
                                            <span className="absolute inset-y-0 left-0 flex items-center pl-3 text-amber-600">
                                              <BsCheckLg
                                                className="h-5 w-5"
                                                aria-hidden="true"
                                              />
                                            </span>
                                          ) : null}
                                        </>
                                      )}
                                    </Listbox.Option>
                                  )
                                )}
                              </Listbox.Options>
                            </Transition>
                          </div>
                        </Listbox>
                      </div>
                      <div className="">
                        If you selected short loaging
                        <Listbox
                          multiple
                          value={selectedShort}
                          onChange={setSelectedShort}
                        >
                          <div className="relative mt-1">
                            <Listbox.Button className="relative w-full cursor-default rounded-lg bg-white py-2 pl-3 pr-10 text-left shadow-md focus:outline-none focus-visible:border-indigo-500 focus-visible:ring-2 focus-visible:ring-white focus-visible:ring-opacity-75 focus-visible:ring-offset-2 focus-visible:ring-offset-orange-300 sm:text-sm z-0">
                              <span className="block truncate">
                                {selectedShort
                                  .map((person) => person.name)
                                  .join(", ") || "Please select a item"}
                              </span>
                              <span className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-2">
                                <HiChevronUpDown
                                  className="h-5 w-5 text-gray-400"
                                  aria-hidden="true"
                                />
                              </span>
                            </Listbox.Button>
                            <Transition
                              as={Fragment}
                              leave="transition ease-in duration-100"
                              leaveFrom="opacity-100"
                              leaveTo="opacity-0"
                            >
                              <Listbox.Options className="absolute mt-1 max-h-60 w-full overflow-auto rounded-md bg-white py-1 text-base shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none sm:text-sm">
                                {ShortLoadingConfigure.map(
                                  (person, personIdx) => (
                                    <Listbox.Option
                                      key={personIdx}
                                      className={({ active }) =>
                                        `relative cursor-default select-none py-2 pl-10 pr-4 ${
                                          active
                                            ? "bg-amber-100 text-amber-900"
                                            : "text-gray-900"
                                        }`
                                      }
                                      value={person}
                                    >
                                      {({ selected }) => (
                                        <>
                                          <span
                                            className={`block truncate ${
                                              selected
                                                ? "font-medium"
                                                : "font-normal"
                                            }`}
                                          >
                                            {person.name}
                                          </span>
                                          {selected ? (
                                            <span className="absolute inset-y-0 left-0 flex items-center pl-3 text-amber-600">
                                              <BsCheckLg
                                                className="h-5 w-5"
                                                aria-hidden="true"
                                              />
                                            </span>
                                          ) : null}
                                        </>
                                      )}
                                    </Listbox.Option>
                                  )
                                )}
                              </Listbox.Options>
                            </Transition>
                          </div>
                        </Listbox>
                      </div>
                      <div className="mt-8 w-full flex items-end flex-col">
                        <button
                          type="submit"
                          className="inline-flex   items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-indigo-700 bg-indigo-100 hover:bg-indigo-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
                        >
                          Submit
                        </button>
                      </div>
                    </div>
                    {/* /End replace */}
                  </div>
                </div>
              </div>
            </Transition.Child>
          </form>
        </div>
      </Dialog>
    </Transition.Root>
  );
}
