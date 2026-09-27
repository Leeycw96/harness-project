import { BOARD_SIZE, createGame, requestTurn, step } from './game.mjs';

const canvas = document.querySelector('#board');
const context = canvas.getContext('2d');
const score = document.querySelector('#score');
const status = document.querySelector('#status');
const start = document.querySelector('#start');
const restart = document.querySelector('#restart');
const message = document.querySelector('#board-message');
const messageTitle = document.querySelector('#message-title');
const messageCopy = document.querySelector('#message-copy');
const cellSize = canvas.width / BOARD_SIZE;
const tickMilliseconds = 150;
const statusText = { READY: '待开始', RUNNING: '进行中', LOST: '游戏结束', WON: '完成：已填满棋盘' };
const keys = { arrowup: 'UP', w: 'UP', arrowdown: 'DOWN', s: 'DOWN', arrowleft: 'LEFT', a: 'LEFT', arrowright: 'RIGHT', d: 'RIGHT' };
let state = createGame();
let timer = null;

function drawCell(cell, color, inset = 2) {
  context.fillStyle = color;
  context.beginPath();
  context.roundRect(cell.x * cellSize + inset, cell.y * cellSize + inset, cellSize - inset * 2, cellSize - inset * 2, 4);
  context.fill();
}

function render() {
  context.fillStyle = '#132b25';
  context.fillRect(0, 0, canvas.width, canvas.height);
  context.strokeStyle = '#20382e';
  context.lineWidth = 1;
  context.beginPath();
  for (let index = 1; index < BOARD_SIZE; index++) {
    const point = index * cellSize + 0.5;
    context.moveTo(point, 0);
    context.lineTo(point, canvas.height);
    context.moveTo(0, point);
    context.lineTo(canvas.width, point);
  }
  context.stroke();
  if (state.food) drawCell(state.food, '#ec8772', 4);
  state.snake.forEach((cell, index) => drawCell(cell, index ? '#9ebb69' : '#d7ef9c'));
  const head = state.snake[0];
  const horizontal = state.direction === 'LEFT' || state.direction === 'RIGHT';
  const forward = state.direction === 'RIGHT' || state.direction === 'DOWN' ? 13 : 7;
  context.fillStyle = '#27422b';
  for (const side of [6, 12]) {
    context.fillRect(head.x * cellSize + (horizontal ? forward : side), head.y * cellSize + (horizontal ? side : forward), 2, 2);
  }
  score.value = String(state.score).padStart(2, '0');
  status.textContent = statusText[state.status];
  status.dataset.status = state.status;
  start.disabled = state.status !== 'READY';
  restart.disabled = state.status === 'READY';
  message.hidden = state.status === 'RUNNING';
  messageTitle.textContent = state.status === 'READY' ? '准备好了吗？' : statusText[state.status];
  messageCopy.textContent = state.status === 'READY' ? '点击「开始游戏」，向前出发' : `本局得到 ${state.score} 分 · 点击「重新开始」再来一局`;
}

function clearTimer() {
  if (timer !== null) window.clearInterval(timer);
  timer = null;
}

function startGame() {
  clearTimer();
  state = createGame('RUNNING');
  render();
  timer = window.setInterval(() => {
    state = step(state);
    render();
    if (state.status !== 'RUNNING') clearTimer();
  }, tickMilliseconds);
}

document.addEventListener('keydown', (event) => {
  const direction = keys[event.key.toLowerCase()];
  if (state.status !== 'RUNNING' || !direction) return;
  event.preventDefault();
  if (!event.repeat) state = requestTurn(state, direction);
});
start.addEventListener('click', startGame);
restart.addEventListener('click', startGame);
render();
