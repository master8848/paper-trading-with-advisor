import { Test, TestingModule } from '@nestjs/testing';
import { StockExchangeService } from './stock-exchange.service';

describe('StockExchangeService', () => {
  let service: StockExchangeService;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [StockExchangeService],
    }).compile();

    service = module.get<StockExchangeService>(StockExchangeService);
  });

  it('should be defined', () => {
    expect(service).toBeDefined();
  });
});
