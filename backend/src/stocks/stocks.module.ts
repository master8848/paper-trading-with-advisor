import { Module } from '@nestjs/common';
import { StocksService } from './stocks.service';
import { StocksController } from './stocks.controller';
import { TypeOrmModule } from '@nestjs/typeorm';
// import { Stock } from './entities/stock.entity';
import { Stocks } from './entities/FinanceData';
// import { StockExchangeService } from 'src/stock-exchange/stock-exchange.service';
import { StockExchangeModule } from 'src/stock-exchange/stock-exchange.module';

@Module({
  imports: [TypeOrmModule.forFeature([Stocks]), StockExchangeModule],
  controllers: [StocksController],
  providers: [StocksService],
})
export class StocksModule {}
