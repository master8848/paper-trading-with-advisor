import { Injectable } from '@nestjs/common';
import { HttpException, HttpStatus } from '@nestjs/common';
@Injectable()
export class AppService {
  getHello(): string {
    throw new HttpException('Please Verify Your Route', HttpStatus.NOT_FOUND);
  }
}
