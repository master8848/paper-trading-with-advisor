import { CacheModule, Module } from '@nestjs/common';
import { StockExchangeService } from './stock-exchange.service';
import { StockExchangeController } from './stock-exchange.controller';

@Module({
  imports: [
    CacheModule.register({
      ttl: 84000,
      max: 10,
    }),
  ],
  controllers: [StockExchangeController],
  providers: [StockExchangeService],
  exports: [StockExchangeService],
})
export class StockExchangeModule {}
