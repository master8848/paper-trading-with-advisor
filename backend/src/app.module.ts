import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { AppController } from './app.controller';
import { AppService } from './app.service';
import { Stocks } from './stocks/entities/FinanceData';
import { StocksModule } from './stocks/stocks.module';
import { StockExchangeModule } from './stock-exchange/stock-exchange.module';

@Module({
  imports: [
    // Legacy NestJS backend — DB config now env-driven (see backend_py/app/database.py).
    // Default is SQLite (finance_app.db) swappable to Postgres via DATABASE_URL.
    // Original MySQL hardcoded creds removed for security — use env DB_* if you still need MySQL.
    TypeOrmModule.forRoot({
      type: (process.env.DB_TYPE as any) || 'sqlite',
      host: process.env.DB_HOST || 'localhost',
      port: parseInt(process.env.DB_PORT || '3306', 10),
      username: process.env.DB_USER || 'Finance',
      password: process.env.DB_PASSWORD || undefined,
      database: process.env.DB_NAME || 'finance_app.db',
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
