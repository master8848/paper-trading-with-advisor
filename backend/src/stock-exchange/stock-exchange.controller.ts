import {
  Controller,
  Get,
  Post,
  Body,
  Patch,
  Param,
  Delete,
  UseInterceptors,
  CacheInterceptor,
} from '@nestjs/common';
import { StockExchangeService } from './stock-exchange.service';

@Controller('stock-exchange')
export class StockExchangeController {
  constructor(private readonly stockExchangeService: StockExchangeService) {}

  @UseInterceptors(CacheInterceptor)
  @Get('Nse')
  getStockExchange() {
    return this.stockExchangeService.findStock();
  }
  @Get(':id')
  async getLastTradedPriceOfStock(@Param('id') id: string) {
    return await this.stockExchangeService.findLastTradedPrice(id);
  }
}
