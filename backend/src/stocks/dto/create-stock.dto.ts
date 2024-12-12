import { IsNotEmpty } from 'class-validator';

export class CreateStockDto {
  @IsNotEmpty()
  username: string;

  message: string;

  @IsNotEmpty()
  price: string;

  @IsNotEmpty()
  stockName: string;

  @IsNotEmpty()
  type: 'buy' | 'sell';

  @IsNotEmpty()
  quantity: string;
}
