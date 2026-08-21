import React from "react";
import { createBrowserRouter } from "react-router-dom";
import Homes from "./Home";
import StockView from "./pages/StockView";
export const Routes = createBrowserRouter([
  {
    path: "/",
    element: <Homes />,
  },
  {
    path: "/stock/:symbol",
    element: <StockView />,
  },
]);
