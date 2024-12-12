import { Injectable } from '@nestjs/common';
import { Http2ServerRequest } from 'http2';
import * as moment from 'moment';
import { NseIndia } from 'stock-nse-india';

@Injectable()
export class StockExchangeService {
  protected nseIndia() {
    return new NseIndia();
  }

  findStock() {
    return this.nseIndia().getAllStockSymbols();
  }
  findEquityHistoricalData(StockSymbole) {
    if (!StockSymbole) return;
    return this.nseIndia().getEquityHistoricalData(StockSymbole, {
      start: moment().subtract(4, 'days').toDate(),
      end: new Date(),
    });
  }
  async findLastTradedPrice(StockSymbole) {
    if (!StockSymbole) return;
    try {
      const allPrice = await this.findEquityHistoricalData(StockSymbole);
      const lastTradedPrice = allPrice[0]?.data[0]?.CH_LAST_TRADED_PRICE;
      const fiftyTwoWeekLow = allPrice[0]?.data[0]?.CH_52WEEK_LOW_PRICE;
      const fiftyTwoWeekHigh = allPrice[0]?.data[0]?.CH_52WEEK_HIGH_PRICE;
      return { lastTradedPrice, fiftyTwoWeekLow, fiftyTwoWeekHigh };
    } catch {
      return;
    }
  }
}
