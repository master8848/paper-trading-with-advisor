import { Inject, Injectable } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Stocks } from 'src/stocks/entities/FinanceData';
import { Between, LessThan, MoreThan, Repository } from 'typeorm';
import { CreateStockDto } from './dto/create-stock.dto';
import { UpdateStockDto } from './dto/update-stock.dto';
import * as moment from 'moment';
import { StockExchangeService } from 'src/stock-exchange/stock-exchange.service';

@Injectable()
export class StocksService {
  @Inject(StockExchangeService)
  private readonly nseService: StockExchangeService;
  constructor(
    @InjectRepository(Stocks) private StockRepository: Repository<Stocks>,
  ) {}
  create(createStockDto: CreateStockDto) {
    return this.StockRepository.save(
      this.StockRepository.create({
        ...createStockDto,
        transactionType: createStockDto.type,
        date: moment().format('YYYY-MM-DD HH:mm:ss'),
        total: +createStockDto.price * +createStockDto.quantity + '',
        modified: moment().format('YYYY-MM-DD HH:mm:ss'),
      }),
    );
  }

  async findAll(query) {
    let resp;

    switch (query?.duration?.toLowerCase()) {
      case 'tweek':
        resp = this.StockRepository.find({
          where: {
            // @ts-ignore
            modified: MoreThan(moment().startOf('week').toISOString()),
          },
        });
        break;

      case 'lweek':
        resp = this.StockRepository.find({
          where: {
            // @ts-ignore
            modified: Between(
              moment().subtract(1, 'week').startOf('week').toISOString(),
              moment().startOf('week').toISOString(),
            ),
          },
        });
        break;

      case 'tmonth':
        resp = this.StockRepository.find({
          where: {
            // @ts-ignore
            modified: MoreThan(moment().startOf('month').toISOString()),
          },
        });
        break;

      case 'lmonth':
        resp = this.StockRepository.find({
          where: {
            // @ts-ignore
            modified: Between(
              moment().subtract(1, 'month').startOf('month').toISOString(),
              moment().startOf('month').toISOString(),
            ),
          },
        });
        break;
      case 'tyear':
        resp = this.StockRepository.find({
          // @ts-ignore
          where: { modified: MoreThan(moment().startOf('year').toISOString()) },
        });

        break;
      case 'lyear':
        resp = this.StockRepository.find({
          where: {
            // @ts-ignore
            modified: Between(
              moment().subtract(1, 'year').startOf('year').toISOString(),
              moment().startOf('year').toISOString(),
            ),
          },
        });

        break;
      default:
        resp = this.StockRepository.find();
        break;
    }
    if (query?.load) {
      resp = await resp;
      resp = await Promise.all(
        resp?.map(async (element) => {
          // return element;
          try {
            const allPrice = await this.nseService.findEquityHistoricalData(
              element.stockName,
            );
            const lastTradedPrice = allPrice[0]?.data[0]?.CH_LAST_TRADED_PRICE;
            const fiftyTwoWeekLow = allPrice[0]?.data[0]?.CH_52WEEK_LOW_PRICE;
            const fiftyTwoWeekHigh = allPrice[0]?.data[0]?.CH_52WEEK_HIGH_PRICE;

            return {
              ...element,
              lastTradedPrice,
              fiftyTwoWeekLow,
              fiftyTwoWeekHigh,
            };
          } catch {
            return element;
          }
        }),
      );
    }

    return resp;
  }

  update(id: number, updateStockDto: UpdateStockDto) {
    // return this.StockRepository.save(
    return this.StockRepository.update(
      { id },
      {
        ...updateStockDto,
        total: +updateStockDto.price * +updateStockDto.quantity + '',
        modified: moment().format('YYYY-MM-DD HH:mm:ss'),
      },
    );
    // );
  }

  remove(id: number) {
    return this.StockRepository.delete({ id });
    // return this.StockRepository.save(deletee);
  }
}
