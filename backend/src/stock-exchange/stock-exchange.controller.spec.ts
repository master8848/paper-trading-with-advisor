import { Test, TestingModule } from '@nestjs/testing';
import { StockExchangeController } from './stock-exchange.controller';
import { StockExchangeService } from './stock-exchange.service';

describe('StockExchangeController', () => {
  let controller: StockExchangeController;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      controllers: [StockExchangeController],
      providers: [StockExchangeService],
    }).compile();

    controller = module.get<StockExchangeController>(StockExchangeController);
  });

  it('should be defined', () => {
    expect(controller).toBeDefined();
  });
});
