---
name: express-prisma-patterns
description: Use when writing or modifying Express + Prisma backend code in VSmartwatch admin (HealthGuard/backend). Reference patterns for Prisma client singleton, JWT auth, route/controller/service layering, error handling, Postgres patterns, Socket.IO realtime, AWS S3, and Jest testing.
---

# Express + Prisma Patterns — VSmartwatch HealthGuard Admin

> Apply when working in `HealthGuard/backend/`. Stack: Node.js (plain JS, **not TypeScript**) + Express + Prisma + Postgres + JWT + Socket.IO + AWS S3.

## Project layering

```
src/
├── server.js              # Express init, middleware, listen
├── routes/                # router definition (URL → controller)
├── controllers/           # parse req → call service → respond (THIN)
├── services/              # business logic + transactions
├── middleware/            # auth, cors, rate-limit, error
├── lib/
│   ├── prisma.js          # PrismaClient singleton
│   ├── logger.js          # winston/pino instance
│   └── errors.js          # AppError classes
├── __tests__/             # jest tests
└── prisma/
    ├── schema.prisma
    └── migrations/
```

## Prisma client — singleton

```js
// src/lib/prisma.js
const { PrismaClient } = require('@prisma/client');

const prisma = new PrismaClient({
  log: process.env.NODE_ENV === 'development'
    ? ['query', 'warn', 'error']
    : ['warn', 'error'],
});

// Graceful shutdown
process.on('beforeExit', async () => { await prisma.$disconnect(); });

module.exports = prisma;
```

**Cấm:** `new PrismaClient()` trong route/service — connection pool exhaustion.

## Routes → Controllers → Services

### Route (thin URL mapping)

```js
// src/routes/devices.js
const router = require('express').Router();
const ctrl = require('../controllers/deviceController');
const { authJWT, requireRole } = require('../middleware/auth');

router.get('/', authJWT, requireRole('admin'), ctrl.list);
router.get('/:id', authJWT, requireRole('admin'), ctrl.getById);
router.post('/', authJWT, requireRole('admin'), ctrl.create);
router.delete('/:id', authJWT, requireRole('admin'), ctrl.remove);

module.exports = router;
```

### Controller (parse + delegate + respond)

```js
// src/controllers/deviceController.js
const deviceService = require('../services/deviceService');

exports.list = async (req, res, next) => {
  try {
    const { page = 1, pageSize = 20, search } = req.query;
    const data = await deviceService.list({ page: +page, pageSize: +pageSize, search });
    res.json(data);
  } catch (err) { next(err); }
};

exports.create = async (req, res, next) => {
  try {
    const device = await deviceService.create(req.body, { actorUserId: req.user.id });
    res.status(201).json(device);
  } catch (err) { next(err); }
};
```

**Don't:** validation, business logic, DB queries trong controller.

### Service (business logic)

```js
// src/services/deviceService.js
const prisma = require('../lib/prisma');
const { ConflictError, NotFoundError } = require('../lib/errors');
const { z } = require('zod');

const createSchema = z.object({
  imei: z.string().regex(/^\d{15}$/),
  model: z.string().min(1),
  userId: z.string().uuid().optional(),
});

exports.create = async (input, { actorUserId }) => {
  const parsed = createSchema.parse(input);
  
  const existing = await prisma.device.findUnique({ where: { imei: parsed.imei } });
  if (existing) throw new ConflictError(`Device IMEI ${parsed.imei} already exists`);
  
  return prisma.$transaction(async (tx) => {
    const device = await tx.device.create({ data: parsed });
    await tx.auditLog.create({
      data: { actorId: actorUserId, action: 'DEVICE_CREATE', resourceId: device.id },
    });
    return device;
  });
};

exports.list = async ({ page, pageSize, search }) => {
  const where = search ? { OR: [
    { imei: { contains: search } },
    { model: { contains: search, mode: 'insensitive' } },
  ]} : {};
  
  const [items, total] = await Promise.all([
    prisma.device.findMany({
      where, skip: (page - 1) * pageSize, take: pageSize,
      orderBy: { createdAt: 'desc' },
      select: { id: true, imei: true, model: true, status: true, userId: true, createdAt: true },
    }),
    prisma.device.count({ where }),
  ]);
  return { items, total, page, pageSize };
};
```

**Use `select` explicit** — không lấy field thừa (security + perf).
**Use `prisma.$transaction`** cho multi-step writes.

## Error model

```js
// src/lib/errors.js
class AppError extends Error {
  constructor(code, message, statusCode, details) {
    super(message);
    this.code = code;
    this.statusCode = statusCode;
    this.details = details;
  }
}
class ValidationError extends AppError { constructor(msg, d) { super('VALIDATION', msg, 400, d); } }
class UnauthenticatedError extends AppError { constructor() { super('UNAUTH', 'Auth required', 401); } }
class ForbiddenError extends AppError { constructor(action) { super('FORBIDDEN', `Cannot ${action}`, 403); } }
class NotFoundError extends AppError { constructor(res) { super('NOT_FOUND', `${res} not found`, 404); } }
class ConflictError extends AppError { constructor(msg) { super('CONFLICT', msg, 409); } }

module.exports = { AppError, ValidationError, UnauthenticatedError, ForbiddenError, NotFoundError, ConflictError };
```

## Global error handler

```js
// src/middleware/errorHandler.js
const { AppError } = require('../lib/errors');
const logger = require('../lib/logger');
const { ZodError } = require('zod');

module.exports = (err, req, res, _next) => {
  // Prisma known errors
  if (err.code === 'P2025') return res.status(404).json({ error: { code: 'NOT_FOUND', message: 'Resource not found' } });
  if (err.code === 'P2002') return res.status(409).json({ error: { code: 'DUPLICATE', message: 'Unique constraint violated' } });
  
  // Zod validation
  if (err instanceof ZodError) {
    return res.status(400).json({ error: { code: 'VALIDATION', message: 'Invalid input', details: err.flatten() } });
  }
  
  // App errors
  if (err instanceof AppError) {
    logger.warn({ code: err.code, path: req.path }, err.message);
    return res.status(err.statusCode).json({ error: { code: err.code, message: err.message, details: err.details } });
  }
  
  // Unknown — DON'T leak stack trace (security)
  logger.error({ err, path: req.path }, 'Unexpected error');
  res.status(500).json({ error: { code: 'INTERNAL', message: 'Internal server error' } });
};
```

## JWT auth middleware

```js
// src/middleware/auth.js
const jwt = require('jsonwebtoken');
const { UnauthenticatedError, ForbiddenError } = require('../lib/errors');

exports.authJWT = (req, _res, next) => {
  const header = req.headers.authorization;
  if (!header?.startsWith('Bearer ')) return next(new UnauthenticatedError());
  
  try {
    const payload = jwt.verify(header.slice(7), process.env.JWT_SECRET, {
      issuer: 'healthguard-admin',
      algorithms: ['HS256'],
    });
    req.user = { id: payload.sub, email: payload.email, role: payload.role };
    next();
  } catch (e) {
    next(new UnauthenticatedError());
  }
};

exports.requireRole = (...roles) => (req, _res, next) => {
  if (!roles.includes(req.user?.role)) return next(new ForbiddenError('access this resource'));
  next();
};
```

## Resource ownership check

```js
// In service — user A cannot read user B's data unless linked
exports.getDeviceForUser = async (deviceId, userId) => {
  const device = await prisma.device.findUnique({
    where: { id: deviceId },
    include: { user: { include: { linkedProfiles: true } } },
  });
  if (!device) throw new NotFoundError('Device');
  
  const ownerId = device.userId;
  const allowedIds = [ownerId, ...(device.user?.linkedProfiles ?? []).map((l) => l.linkedUserId)];
  if (!allowedIds.includes(userId)) throw new ForbiddenError('view this device');
  
  return device;
};
```

## Migrations

```pwsh
# cwd: d:\DoAn2\VSmartwatch\HealthGuard\backend
npx prisma migrate dev --name add_device_status   # dev — auto-apply
npx prisma migrate deploy                         # production — CI/CD
npx prisma generate                               # after schema change
```

**Cấm:** edit committed migration file. Tạo migration mới thay.
**Sync:** SQL canonical ở `PM_REVIEW/SQL SCRIPTS/` — verify diverge khi schema change.

## Socket.IO realtime (vital monitor)

```js
// src/realtime/socketServer.js
const { Server } = require('socket.io');
const jwt = require('jsonwebtoken');

function attach(httpServer) {
  const io = new Server(httpServer, {
    cors: { origin: process.env.ALLOWED_ORIGINS.split(','), credentials: true },
  });
  
  io.use((socket, next) => {
    try {
      const token = socket.handshake.auth?.token;
      if (!token) throw new Error('No token');
      const payload = jwt.verify(token, process.env.JWT_SECRET);
      socket.data.user = { id: payload.sub, role: payload.role };
      next();
    } catch (e) { next(new Error('UNAUTH')); }
  });
  
  io.on('connection', (socket) => {
    socket.join(`user:${socket.data.user.id}`);  // private room — don't broadcast
    socket.on('subscribe:device', (deviceId) => {
      // verify ownership before joining
      socket.join(`device:${deviceId}`);
    });
  });
  return io;
}

module.exports = { attach };
```

**Don't broadcast** to all clients — always emit to specific room (`device:<id>` or `user:<id>`).

## AWS S3 — pre-signed URL only

```js
// src/services/uploadService.js
const { S3Client, PutObjectCommand } = require('@aws-sdk/client-s3');
const { getSignedUrl } = require('@aws-sdk/s3-request-presigner');

exports.getUploadUrl = async ({ filename, contentType, userId }) => {
  const key = `users/${userId}/${Date.now()}-${filename}`;
  const cmd = new PutObjectCommand({
    Bucket: process.env.S3_BUCKET,
    Key: key,
    ContentType: contentType,
  });
  const url = await getSignedUrl(s3, cmd, { expiresIn: 300 });
  return { uploadUrl: url, key };
};
```

**Cấm:** proxy file qua backend (memory bloat). Client upload trực tiếp tới S3 với pre-signed URL.

## Testing (Jest)

```js
// src/__tests__/deviceService.test.js
const { mockDeep, mockReset } = require('jest-mock-extended');
const prismaMock = mockDeep();

jest.mock('../lib/prisma', () => prismaMock);

const deviceService = require('../services/deviceService');

beforeEach(() => mockReset(prismaMock));

describe('deviceService.create', () => {
  test('throws ConflictError on duplicate IMEI', async () => {
    prismaMock.device.findUnique.mockResolvedValue({ id: 'd1', imei: '123456789012345' });
    await expect(deviceService.create({ imei: '123456789012345', model: 'X' }, { actorUserId: 'u1' }))
      .rejects.toThrow(/already exists/);
  });
});
```

Run: `npm test -- deviceService.test.js` (focused) trước `npm test` (full).

## Common gotchas

| Issue | Fix |
|---|---|
| `new PrismaClient()` everywhere | Singleton `lib/prisma.js` |
| `app.use(cors())` no config | Whitelist origin from env, never `*` in prod |
| Missing `await` on async route | Use try/catch + `next(err)` or `express-async-errors` package |
| Prisma error leaking to client | Map P2002/P2025/etc in `errorHandler` |
| `console.log` in production | Use `lib/logger.js` (winston/pino), structured |
| Stack trace in 500 response | `errorHandler` returns generic message; log details internally |
| JWT secret hardcoded | `process.env.JWT_SECRET` validated at startup |
| Socket broadcast to all | `socket.to('room:id').emit(...)` — never `io.emit` |
| `JSON.parse` on user input | Wrap in try/catch + ValidationError |

## Quick commands

```pwsh
# cwd: d:\DoAn2\VSmartwatch\HealthGuard\backend
npm install
npm run dev                                       # nodemon
npx prisma generate                               # after schema change
npx prisma migrate dev --name <desc>              # new migration
npx prisma studio                                 # DB GUI (dev only)
npm test -- <file>                                # focused
npm test                                          # full suite
npm run lint
```

## Anti-patterns auto-flag

- `new PrismaClient()` outside singleton
- `app.use(cors())` without origin config (prod)
- SQL string concat (always use Prisma parameterized)
- `console.log` in production code
- `JSON.parse` on user input without try/catch
- Missing `await` on async DB call
- Hardcoded JWT secret / API key
- `io.emit` broadcast (use room-based)
- `JSON.stringify(err.stack)` in API response
