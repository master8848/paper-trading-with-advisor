import React from "react";
import { createBrowserRouter } from "react-router-dom";
import Homes from "./Home";
export const Routes = createBrowserRouter([
  {
    path: "/",
    element: <Homes />,
  },
]);
