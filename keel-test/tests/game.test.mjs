import test from 'node:test';
import assert from 'node:assert/strict';
import { BOARD_SIZE, createGame, requestTurn, step } from '../game.mjs';

const first = () => 0;
const running = () => createGame('RUNNING', first);
const freeze = (value) => {
  if (value && typeof value === 'object') {
    Object.values(value).forEach(freeze);
    Object.freeze(value);
  }
  return value;
};

test('待开始和运行新局都从固定蛇身、方向及零分建立', () => {
  for (const status of ['READY', 'RUNNING']) {
    const state = createGame(status, first);
    assert.equal(BOARD_SIZE, 20);
    assert.equal(state.status, status);
    assert.deepEqual(state.snake, [{ x: 10, y: 10 }, { x: 9, y: 10 }, { x: 8, y: 10 }]);
    assert.equal(state.direction, 'RIGHT');
    assert.equal(state.pendingDirection, null);
    assert.equal(state.score, 0);
    assert.deepEqual(state.food, { x: 0, y: 0 });
  }
  assert.equal(createGame().status, 'READY');
});

test('食物从空格枚举中选取，随机源两端均不会选中蛇身', () => {
  for (const value of [0, 0.51, 1 - Number.EPSILON]) {
    const state = createGame('RUNNING', () => value);
    assert.ok(state.food.x >= 0 && state.food.x < 20);
    assert.ok(state.food.y >= 0 && state.food.y < 20);
    assert.ok(!state.snake.some(({ x, y }) => x === state.food.x && y === state.food.y));
  }
  assert.deepEqual(createGame('RUNNING', () => 1 - Number.EPSILON).food, { x: 19, y: 19 });
});

test('同向和反向请求不消耗转向机会，随后合法请求可应用', () => {
  const state = freeze(running());
  assert.equal(requestTurn(state, 'RIGHT'), state);
  assert.equal(requestTurn(state, 'LEFT'), state);
  assert.equal(requestTurn(state, 'UNKNOWN'), state);
  const turned = requestTurn(requestTurn(state, 'LEFT'), 'UP');
  assert.equal(turned.pendingDirection, 'UP');
  assert.equal(state.pendingDirection, null);
});

test('每步只接收首个合法转向，连续右上左不能绕过反向限制', () => {
  const up = requestTurn(running(), 'UP');
  assert.equal(requestTurn(up, 'LEFT'), up);
  assert.equal(requestTurn(up, 'DOWN'), up);
  const moved = step(freeze(up), first);
  assert.deepEqual(moved.snake[0], { x: 10, y: 9 });
  assert.equal(moved.direction, 'UP');
  assert.equal(moved.pendingDirection, null);
  assert.equal(requestTurn(moved, 'LEFT').pendingDirection, 'LEFT');
});

test('四个方向的垂直转向均可用，每个方向都禁止直接掉头', () => {
  const opposites = { RIGHT: 'LEFT', LEFT: 'RIGHT', UP: 'DOWN', DOWN: 'UP' };
  for (const direction of Object.keys(opposites)) {
    const state = { ...running(), direction };
    assert.equal(requestTurn(state, opposites[direction]), state);
    for (const desired of Object.keys(opposites)) {
      if (desired !== direction && desired !== opposites[direction]) {
        assert.equal(requestTurn(state, desired).pendingDirection, desired);
      }
    }
  }
});

test('普通移动加入蛇头并移走尾巴，不改长度、食物、分数和输入状态', () => {
  const state = freeze(running());
  const moved = step(state, first);
  assert.deepEqual(moved.snake, [{ x: 11, y: 10 }, { x: 10, y: 10 }, { x: 9, y: 10 }]);
  assert.equal(moved.score, 0);
  assert.deepEqual(moved.food, state.food);
  assert.equal(moved.status, 'RUNNING');
  assert.deepEqual(state.snake[0], { x: 10, y: 10 });
});

test('吃食物保留尾巴、增长一格、加一分，并从空格生成新食物', () => {
  const state = freeze({ ...running(), food: { x: 11, y: 10 } });
  const moved = step(state, () => 0.52);
  assert.equal(moved.snake.length, 4);
  assert.deepEqual(moved.snake.at(-1), { x: 8, y: 10 });
  assert.equal(moved.score, 1);
  assert.equal(moved.status, 'RUNNING');
  assert.ok(!moved.snake.some(({ x, y }) => x === moved.food.x && y === moved.food.y));
  assert.equal(state.score, 0);
});

test('四面撞墙都结束并保留最后的合法棋盘和得分', () => {
  const walls = [
    ['RIGHT', { x: 19, y: 10 }], ['LEFT', { x: 0, y: 10 }],
    ['UP', { x: 10, y: 0 }], ['DOWN', { x: 10, y: 19 }],
  ];
  for (const [direction, head] of walls) {
    const state = freeze({ ...running(), direction, snake: [head], score: 4 });
    const ended = step(state, first);
    assert.equal(ended.status, 'LOST');
    assert.deepEqual(ended.snake, state.snake);
    assert.deepEqual(ended.food, state.food);
    assert.equal(ended.score, 4);
  }
});

test('撞到仍占用的身体格结束且不插入非法蛇头', () => {
  const state = freeze({ ...running(), direction: 'UP', pendingDirection: 'LEFT',
    snake: [{ x: 2, y: 1 }, { x: 2, y: 2 }, { x: 1, y: 2 }, { x: 1, y: 1 }, { x: 0, y: 1 }] });
  const ended = step(state, first);
  assert.equal(ended.status, 'LOST');
  assert.deepEqual(ended.snake, state.snake);
  assert.equal(ended.pendingDirection, null);
  assert.equal(ended.score, 0);
});

test('未吃食物时允许进入本步移走的尾格', () => {
  const state = freeze({ ...running(), direction: 'UP', pendingDirection: 'RIGHT',
    snake: [{ x: 1, y: 1 }, { x: 1, y: 2 }, { x: 2, y: 2 }, { x: 2, y: 1 }] });
  const moved = step(state, first);
  assert.equal(moved.status, 'RUNNING');
  assert.deepEqual(moved.snake, [{ x: 2, y: 1 }, { x: 1, y: 1 }, { x: 1, y: 2 }, { x: 2, y: 2 }]);
});

test('增长占满棋盘时完成、397 分、无食物且不再调用随机源', () => {
  const snake = [];
  for (let x = 18; x >= 0; x--) snake.push({ x, y: 0 });
  for (let y = 1; y < 20; y++) {
    for (let i = 0; i < 20; i++) snake.push({ x: y % 2 ? i : 19 - i, y });
  }
  const state = freeze({ ...running(), snake, score: 396, food: { x: 19, y: 0 } });
  const won = step(state, () => { throw new Error('满盘不应生成食物'); });
  assert.equal(won.status, 'WON');
  assert.equal(won.snake.length, 400);
  assert.equal(new Set(won.snake.map(({ x, y }) => `${x},${y}`)).size, 400);
  assert.equal(won.score, 397);
  assert.equal(won.food, null);
});

test('待开始、碰撞结束和满盘状态忽略推进与转向', () => {
  for (const status of ['READY', 'LOST', 'WON']) {
    const state = freeze({ ...running(), status });
    assert.equal(step(state, () => { throw new Error('不应生成食物'); }), state);
    assert.equal(requestTurn(state, 'UP'), state);
  }
});

test('建立新局不继承上一局的分数、方向或蛇身', () => {
  const old = step({ ...running(), food: { x: 11, y: 10 } }, first);
  const fresh = createGame('RUNNING', first);
  assert.equal(old.score, 1);
  assert.equal(fresh.score, 0);
  assert.equal(fresh.direction, 'RIGHT');
  assert.equal(fresh.pendingDirection, null);
  assert.equal(fresh.snake.length, 3);
  assert.notEqual(fresh.snake, old.snake);
});
