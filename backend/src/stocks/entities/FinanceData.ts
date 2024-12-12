import { Entity, PrimaryGeneratedColumn, Column } from 'typeorm';

export enum TypeOfTransaction {
  Buy = 'buy',
  Sell = 'sell',
}
@Entity({ name: 'Stocks' })
export class Stocks {
  @PrimaryGeneratedColumn()
  id: number;
  @Column()
  username: string;
  @Column({ nullable: true })
  message: string;
  @Column()
  price: string;
  @Column()
  stockName: string;
  @Column()
  date: Date;
  @Column()
  modified: Date;

  @Column({
    type: 'enum',
    enum: TypeOfTransaction,
    default: TypeOfTransaction.Buy,
  })
  transactionType: 'buy' | 'sell';

  @Column()
  quantity: string;
  @Column()
  total: string;
}
