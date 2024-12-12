import { PartialType } from '@nestjs/mapped-types';
import { IsNotEmpty } from 'class-validator';
import { CreateStockDto } from './create-stock.dto';

export class UpdateStockDto extends PartialType(CreateStockDto) {
  message?: string;

  @IsNotEmpty()
  price: string;

  @IsNotEmpty()
  type: 'buy' | 'sell';

  @IsNotEmpty()
  quantity: string;
}
