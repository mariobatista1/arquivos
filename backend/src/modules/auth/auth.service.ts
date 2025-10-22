import { Injectable, UnauthorizedException } from "@nestjs/common";
import { JwtService } from "@nestjs/jwt";
import { ConfigService } from "@nestjs/config";
import { UsersService } from "../users/users.service";
import { User } from "../users/entities/user.entity";
import { LoginDto } from "./dto/login.dto";

export interface JwtPayload {
  sub: number;
  email: string;
  role: string;
  workspaceId?: number;
  isInternal: boolean;
}

export interface AuthResponse {
  access_token: string;
  refresh_token: string;
  user: {
    id: number;
    email: string;
    role: string;
    workspaceId?: number;
    isInternal: boolean;
  };
}

@Injectable()
export class AuthService {
  constructor(
    private readonly usersService: UsersService,
    private readonly jwtService: JwtService,
    private readonly configService: ConfigService
  ) {}

  async validateUser(email: string, password: string): Promise<User | null> {
    try {
      const user = await this.usersService.findByEmail(email);

      if (!user.isActive) {
        throw new UnauthorizedException("User account is disabled");
      }

      // Check if user's workspace is active (except for super admin)
      if (
        user.workspace &&
        !user.workspace.isActive &&
        user.email !== "admin@playercore.com.br"
      ) {
        throw new UnauthorizedException(
          "Workspace is inactive - access denied"
        );
      }

      // Check failed attempts (simple brute force protection)
      if (user.failedAttempts >= 5) {
        throw new UnauthorizedException(
          "Account locked due to too many failed attempts"
        );
      }

      const isPasswordValid = await this.usersService.validatePassword(
        user,
        password
      );

      if (isPasswordValid) {
        await this.usersService.resetFailedAttempts(user.id);
        await this.usersService.updateLastLogin(user.id);
        return user;
      } else {
        await this.usersService.incrementFailedAttempts(user.id);
        throw new UnauthorizedException("Invalid credentials");
      }
    } catch (error) {
      if (error instanceof UnauthorizedException) {
        throw error;
      }
      throw new UnauthorizedException("Invalid credentials");
    }
  }

  async login(loginDto: LoginDto): Promise<AuthResponse> {
    const user = await this.validateUser(loginDto.email, loginDto.password);

    if (!user) {
      throw new UnauthorizedException("Invalid credentials");
    }

    const payload: JwtPayload = {
      sub: user.id,
      email: user.email,
      role: user.role,
      workspaceId: user.workspaceId,
      isInternal: user.isInternal,
    };

    const accessToken = this.jwtService.sign(payload);
    const refreshToken = this.jwtService.sign(payload, {
      secret: this.configService.get<string>("JWT_REFRESH_SECRET"),
      expiresIn: this.configService.get<string>(
        "JWT_REFRESH_EXPIRES_IN",
        "7d"
      ) as any,
    });

    return {
      access_token: accessToken,
      refresh_token: refreshToken,
      user: {
        id: user.id,
        email: user.email,
        role: user.role,
        workspaceId: user.workspaceId,
        isInternal: user.isInternal,
      },
    };
  }

  async refreshToken(refreshToken: string): Promise<AuthResponse> {
    try {
      const payload = this.jwtService.verify(refreshToken, {
        secret: this.configService.get<string>("JWT_REFRESH_SECRET"),
      });

      const user = await this.usersService.findOne(payload.sub);

      if (!user.isActive) {
        throw new UnauthorizedException("User account is disabled");
      }

      // Check if user's workspace is active (except for super admin)
      if (
        user.workspace &&
        !user.workspace.isActive &&
        user.email !== "admin@playercore.com.br"
      ) {
        throw new UnauthorizedException(
          "Workspace is inactive - access denied"
        );
      }

      const newPayload: JwtPayload = {
        sub: user.id,
        email: user.email,
        role: user.role,
        workspaceId: user.workspaceId,
        isInternal: user.isInternal,
      };

      const newAccessToken = this.jwtService.sign(newPayload);
      const newRefreshToken = this.jwtService.sign(newPayload, {
        secret: this.configService.get<string>("JWT_REFRESH_SECRET"),
        expiresIn: this.configService.get<string>(
          "JWT_REFRESH_EXPIRES_IN",
          "7d"
        ) as any,
      });

      return {
        access_token: newAccessToken,
        refresh_token: newRefreshToken,
        user: {
          id: user.id,
          email: user.email,
          role: user.role,
          workspaceId: user.workspaceId,
          isInternal: user.isInternal,
        },
      };
    } catch (error) {
      throw new UnauthorizedException("Invalid refresh token");
    }
  }

  async getProfile(userId: number): Promise<User> {
    return this.usersService.findOne(userId);
  }

  async resetAdminAttempts(): Promise<void> {
    console.log("🔧 Resetting admin failed attempts...");
    const adminUser = await this.usersService.findByEmail(
      "admin@playercore.com.br"
    );
    if (adminUser) {
      await this.usersService.resetFailedAttempts(adminUser.id);
      console.log("✅ Admin failed attempts reset successfully");
    } else {
      console.log("❌ Admin user not found");
    }
  }

  async updateAdminPassword(): Promise<void> {
    console.log("🔧 Updating admin password...");
    const adminUser = await this.usersService.findByEmail(
      "admin@playercore.com.br"
    );
    if (adminUser) {
      await this.usersService.update(adminUser.id, { password: "Admin@123" });
      console.log("✅ Admin password updated successfully");
    } else {
      console.log("❌ Admin user not found");
    }
  }
}
