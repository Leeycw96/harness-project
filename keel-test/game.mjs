export const BOARD_SIZE = 20;

const vectors = {
  UP: { x: 0, y: -1 }, DOWN: { x: 0, y: 1 },
  LEFT: { x: -1, y: 0 }, RIGHT: { x: 1, y: 0 },
};
const sameCell = (a, b) => a.x === b.x && a.y === b.y;

function createFood(snake, random) {
  const occupied = new Set(snake.map(({ x, y }) => y * BOARD_SIZE + x));
  const empty = [];
  for (let y = 0; y < BOARD_SIZE; y++) {
    for (let x = 0; x < BOARD_SIZE; x++) {
      if (!occupied.has(y * BOARD_SIZE + x)) empty.push({ x, y });
    }
  }
  return empty.length ? empty[Math.floor(random() * empty.length)] : null;
}

// 随机源遵循 Math.random 的 [0, 1) 范围，可注入以复现规则测试。
export function createGame(status = 'READY', random = Math.random) {
  const snake = [{ x: 10, y: 10 }, { x: 9, y: 10 }, { x: 8, y: 10 }];
  return {
    status, snake, direction: 'RIGHT', pendingDirection: null,
    food: createFood(snake, random), score: 0,
  };
}

export function requestTurn(state, direction) {
  if (state.status !== 'RUNNING' || state.pendingDirection || !Object.hasOwn(vectors, direction)) return state;
  const current = vectors[state.direction];
  const desired = vectors[direction];
  if (current.x * desired.x + current.y * desired.y !== 0) return state;
  return { ...state, pendingDirection: direction };
}

export function step(state, random = Math.random) {
  if (state.status !== 'RUNNING') return state;
  const direction = state.pendingDirection ?? state.direction;
  const vector = vectors[direction];
  const head = { x: state.snake[0].x + vector.x, y: state.snake[0].y + vector.y };
  const eating = state.food !== null && sameCell(head, state.food);
  // 不增长时尾格会同时移走，因此它不属于本步的障碍。
  const occupied = eating ? state.snake : state.snake.slice(0, -1);
  const outside = head.x < 0 || head.y < 0 || head.x >= BOARD_SIZE || head.y >= BOARD_SIZE;
  if (outside || occupied.some((cell) => sameCell(cell, head))) {
    return { ...state, status: 'LOST', direction, pendingDirection: null };
  }
  const snake = [head, ...state.snake];
  if (!eating) snake.pop();
  const won = snake.length === BOARD_SIZE * BOARD_SIZE;
  return {
    status: won ? 'WON' : 'RUNNING', snake, direction, pendingDirection: null,
    food: won ? null : eating ? createFood(snake, random) : state.food,
    score: state.score + (eating ? 1 : 0),
  };
}
