---
name: nodejs-ts-backend
description: Use when writing or modifying Node.js + TypeScript backend code (Cloud Functions or standalone API). Patterns for env validation, error handling, logging, testing, and Express middleware.
---

# Node.js + TypeScript Backend Patterns

> Custom skill for Cloud Functions and (optional) the standalone BE of Meep.

## Setup baseline

### `package.json`

```json
{
  "type": "module",
  "engines": { "node": ">=20" },
  "scripts": {
    "build": "tsc",
    "test": "vitest run",
    "test:watch": "vitest",
    "lint": "eslint src --ext .ts",
    "dev": "tsx watch src/index.ts"
  },
  "dependencies": {
    "zod": "^3.23.0",
    "pino": "^9.0.0"
  },
  "devDependencies": {
    "typescript": "^5.4.0",
    "vitest": "^1.6.0",
    "@types/node": "^20.0.0",
    "tsx": "^4.0.0",
    "eslint": "^9.0.0",
    "@typescript-eslint/eslint-plugin": "^7.0.0"
  }
}
```

### `tsconfig.json` — strict mode required

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "outDir": "./dist",
    "rootDir": "./src",
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "noImplicitOverride": true,
    "noFallthroughCasesInSwitch": true,
    "exactOptionalPropertyTypes": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "resolveJsonModule": true,
    "declaration": true,
    "sourceMap": true
  },
  "include": ["src/**/*"]
}
```

## Env validation with zod

```ts
// src/config/env.ts
import { z } from 'zod';

const envSchema = z.object({
  NODE_ENV: z.enum(['development', 'test', 'production']),
  PORT: z.coerce.number().int().positive().default(3000),
  FIREBASE_PROJECT_ID: z.string().min(1),
  FIREBASE_SERVICE_ACCOUNT_PATH: z.string().min(1),
  ALLOWED_ORIGINS: z.string().transform((s) => s.split(',').map((o) => o.trim())),
  LOG_LEVEL: z.enum(['debug', 'info', 'warn', 'error']).default('info'),
});

export type Env = z.infer<typeof envSchema>;

export function loadEnv(): Env {
  const result = envSchema.safeParse(process.env);
  if (!result.success) {
    console.error('❌ Invalid env vars:', result.error.flatten().fieldErrors);
    process.exit(1);
  }
  return result.data;
}

export const env = loadEnv();
```

**Fail fast at startup** instead of crashing mid-request because of a missing env.

## Error model

```ts
// src/lib/errors.ts
export class AppError extends Error {
  constructor(
    public readonly code: string,
    public readonly message: string,
    public readonly statusCode: number,
    public readonly cause?: unknown,
  ) {
    super(message);
    this.name = 'AppError';
  }
}

export class ValidationError extends AppError {
  constructor(message: string, cause?: unknown) {
    super('VALIDATION_ERROR', message, 400, cause);
  }
}

export class UnauthenticatedError extends AppError {
  constructor() {
    super('UNAUTHENTICATED', 'Authentication required', 401);
  }
}

export class ForbiddenError extends AppError {
  constructor(action: string) {
    super('FORBIDDEN', `Not allowed to ${action}`, 403);
  }
}

export class NotFoundError extends AppError {
  constructor(resource: string) {
    super('NOT_FOUND', `${resource} not found`, 404);
  }
}
```

## Express handler pattern (if using a standalone BE)

```ts
// src/middleware/asyncHandler.ts
import type { Request, Response, NextFunction, RequestHandler } from 'express';

export function asyncHandler<T extends RequestHandler>(fn: T): RequestHandler {
  return (req, res, next) => {
    Promise.resolve(fn(req, res, next)).catch(next);
  };
}
```

```ts
// src/middleware/errorHandler.ts
import type { ErrorRequestHandler } from 'express';
import { AppError } from '../lib/errors.js';
import { logger } from '../lib/logger.js';

export const errorHandler: ErrorRequestHandler = (err, req, res, _next) => {
  if (err instanceof AppError) {
    logger.warn({ code: err.code, path: req.path }, err.message);
    return res.status(err.statusCode).json({
      error: { code: err.code, message: err.message },
    });
  }
  logger.error({ err, path: req.path }, 'unexpected error');
  res.status(500).json({ error: { code: 'INTERNAL', message: 'Internal server error' } });
};
```

```ts
// src/routes/posts.ts
import { Router } from 'express';
import { z } from 'zod';
import { asyncHandler } from '../middleware/asyncHandler.js';
import { authenticate } from '../middleware/auth.js';
import { ValidationError } from '../lib/errors.js';

const createPostSchema = z.object({
  caption: z.string().min(1).max(200),
  imageUrl: z.string().url(),
});

export const postsRouter = Router();

postsRouter.post('/', authenticate, asyncHandler(async (req, res) => {
  const parsed = createPostSchema.safeParse(req.body);
  if (!parsed.success) {
    throw new ValidationError('Invalid post data', parsed.error.flatten());
  }
  const post = await postService.create({
    authorId: req.user.uid,
    ...parsed.data,
  });
  res.status(201).json(post);
}));
```

## Cloud Functions v2 pattern

```ts
// functions/src/index.ts
import { setGlobalOptions } from 'firebase-functions/v2';
import { onCall, HttpsError } from 'firebase-functions/v2/https';
import { onDocumentCreated } from 'firebase-functions/v2/firestore';
import { initializeApp } from 'firebase-admin/app';
import { z } from 'zod';

initializeApp();
setGlobalOptions({ region: 'asia-southeast1', maxInstances: 10 });

const sendFriendRequestSchema = z.object({
  toUid: z.string().min(1),
});

export const sendFriendRequest = onCall(async (request) => {
  if (!request.auth) throw new HttpsError('unauthenticated', 'Login required');

  const parsed = sendFriendRequestSchema.safeParse(request.data);
  if (!parsed.success) throw new HttpsError('invalid-argument', parsed.error.message);

  // ... business logic
  return { ok: true };
});

export const onPostCreated = onDocumentCreated('posts/{postId}', async (event) => {
  // ... fan-out notification
});
```

**Cold-start optimization:**

```ts
// Lazy-import expensive libs
let sharp: typeof import('sharp') | null = null;

export const resizeImage = onObjectFinalized(async (event) => {
  if (!sharp) sharp = await import('sharp').then((m) => m.default);
  // use sharp
});
```

## Logger with pino

```ts
// src/lib/logger.ts
import pino from 'pino';
import { env } from '../config/env.js';

export const logger = pino({
  level: env.LOG_LEVEL,
  base: { service: 'meep-api', env: env.NODE_ENV },
  timestamp: pino.stdTimeFunctions.isoTime,
  // pretty in dev
  transport: env.NODE_ENV === 'development' ? {
    target: 'pino-pretty',
    options: { colorize: true },
  } : undefined,
});
```

**No `console.log` in production code.** Use `logger`.

**Don't log PII** (email, phone, message content) in production logs.

## Testing with Vitest

```ts
// src/services/postService.test.ts
import { describe, test, expect, beforeEach } from 'vitest';
import { PostService } from './postService.js';
import { FakeFirestore } from '../testing/fakeFirestore.js';

describe('PostService.create', () => {
  let service: PostService;
  let firestore: FakeFirestore;

  beforeEach(() => {
    firestore = new FakeFirestore();
    service = new PostService({ firestore });
  });

  test('rejects empty caption', async () => {
    await expect(
      service.create({ authorId: 'u1', caption: '', imageUrl: 'x.jpg' })
    ).rejects.toThrow(/caption.*required/i);
  });

  test('persists with serverTimestamp', async () => {
    await service.create({ authorId: 'u1', caption: 'hi', imageUrl: 'x.jpg' });
    const docs = await firestore.collection('posts').get();
    expect(docs.docs).toHaveLength(1);
    expect(docs.docs[0].data().createdAt).toBeDefined();
  });
});
```

## Common gotchas

| Issue | Fix |
|---|---|
| `Cannot use import statement` | `"type": "module"` in package.json + `.js` extension on import paths |
| `process.env.X` undefined at runtime | Validate with zod at startup, fail fast |
| Memory leak from streams / listeners | Always clean up in shutdown handlers |
| Express `res` not sent but `next()` called | `asyncHandler` wraps errors into `errorHandler` |
| Firebase Admin SDK initialised multiple times | Init once at module top, not in handlers |
| Cloud Function timeout | Set `timeoutSeconds` explicitly. Long task → Cloud Tasks / Pub/Sub |
