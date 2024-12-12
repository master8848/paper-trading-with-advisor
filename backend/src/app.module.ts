import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { AppController } from './app.controller';
import { AppService } from './app.service';
import { Stocks } from './stocks/entities/FinanceData';
import { StocksModule } from './stocks/stocks.module';
import { StockExchangeModule } from './stock-exchange/stock-exchange.module';

@Module({
  imports: [
    TypeOrmModule.forRoot({
      type: 'mysql',
      host: 'localhost',
      port: 3306,
      username: 'Finance',
      password: '***REDACTED***',
      database: 'finance_app',
      entities: [Stocks],
      // synchronize: true,
      migrationsRun: true,
      // migrationsRun: false,
    }),
    StocksModule,
    StockExchangeModule,
  ],
  controllers: [AppController],
  providers: [AppService],
})
export class AppModule {}
