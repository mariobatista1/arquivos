import { Module } from "@nestjs/common";
import { JwtModule } from "@nestjs/jwt";
import { PassportModule } from "@nestjs/passport";
import { TypeOrmModule } from "@nestjs/typeorm";
import { ConfigModule, ConfigService } from "@nestjs/config";
import { AuthService } from "./auth.service";
import { AuthController } from "./auth.controller";
import { UsersModule } from "../users/users.module";
import { JwtStrategy } from "./strategies/jwt.strategy";
import { LocalStrategy } from "./strategies/local.strategy";
import { TokensBlacklist } from "./entities/tokens-blacklist.entity";
import { AuditLogs } from "./entities/audit-logs.entity";
import { TokensBlacklistService } from "./services/tokens-blacklist.service";
import { AuditLogsService } from "./services/audit-logs.service";

@Module({
  imports: [
    UsersModule,
    PassportModule,
    TypeOrmModule.forFeature([TokensBlacklist, AuditLogs]),
    JwtModule.registerAsync({
      imports: [ConfigModule],
      useFactory: async (configService: ConfigService) => ({
        secret: configService.get<string>("JWT_SECRET"),
        signOptions: {
          expiresIn: configService.get<string>("JWT_EXPIRES_IN", "15m") as any,
        },
      }),
      inject: [ConfigService],
    }),
  ],
  providers: [
    AuthService,
    LocalStrategy,
    JwtStrategy,
    TokensBlacklistService,
    AuditLogsService,
  ],
  controllers: [AuthController],
  exports: [AuthService, TokensBlacklistService, AuditLogsService],
})
export class AuthModule {}
