import { createSlice } from "@reduxjs/toolkit";

export interface CounterState {
  longLoaded: string[];
  shortLoaded: string[];
}

const initialState: CounterState = {
  longLoaded: ["lastTradedPrice", "modified", "price", "fiftyTwoWeekLow"],
  shortLoaded: ["price", "date", "modified"],
};

export const counterSlice = createSlice({
  name: "tableConfig",
  initialState,
  reducers: {
    setLongLoaded: (state, action) => {
      state.longLoaded = action.payload;
    },
    setShortLoaded: (state, action) => {
      state.shortLoaded = action.payload;
    },
  },
});

// Action creators are generated for each case reducer function
export const { setLongLoaded, setShortLoaded } = counterSlice.actions;

export default counterSlice.reducer;
