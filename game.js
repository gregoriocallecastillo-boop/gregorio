const canvas = document.getElementById('game');
const ctx = canvas.getContext('2d');

const ui = {
  level: document.getElementById('level'),
  lives: document.getElementById('lives'),
  coins: document.getElementById('coins'),
  timer: document.getElementById('timer'),
  message: document.getElementById('message'),
};

const GRAVITY = 0.55;
const keys = {};
const MAX_LEVELS = 10;

const player = {
  x: 70,
  y: 420,
  w: 34,
  h: 42,
  dx: 0,
  dy: 0,
  speed: 4,
  jump: -11.5,
  grounded: false,
  lives: 3,
  coins: 0,
};

let levelIndex = 0;
let levelTimer = 120;
let lastTimerTick = performance.now();
let gameWon = false;

const levelTemplates = [
  { platforms: [[0,500,960,40],[120,430,140,20],[320,380,150,20],[560,330,120,20],[770,280,130,20]], coins:[[150,390],[360,340],[590,290],[810,240]], enemies:[[460,470,90,1.4]] },
  { platforms: [[0,500,960,40],[180,440,120,20],[360,390,140,20],[590,340,120,20],[780,290,130,20],[520,250,80,16]], coins:[[205,400],[390,350],[620,300],[820,250],[545,220]], enemies:[[250,470,120,1.8],[650,310,100,1.2]] },
  { platforms: [[0,500,960,40],[80,430,90,20],[230,390,110,20],[400,350,120,20],[580,310,120,20],[760,260,110,20],[500,220,80,16]], coins:[[100,390],[250,350],[430,310],[620,270],[780,220],[525,190]], enemies:[[420,470,120,2.1],[780,230,70,1.6]] },
  { platforms: [[0,500,960,40],[140,450,160,20],[340,420,90,16],[500,380,120,20],[670,340,140,20],[850,300,90,16],[350,280,90,16]], coins:[[180,410],[360,390],[530,340],[710,300],[870,260],[375,250]], enemies:[[150,420,130,1.6],[670,310,100,2.2]] },
  { platforms: [[0,500,960,40],[90,450,100,20],[240,400,100,20],[390,350,100,20],[540,300,100,20],[690,250,100,20],[840,200,100,20],[680,380,120,20]], coins:[[120,410],[270,360],[420,310],[570,260],[720,210],[870,160],[710,340]], enemies:[[390,470,160,2.4],[700,350,90,1.8]] },
  { platforms: [[0,500,960,40],[180,455,110,20],[340,420,110,20],[500,385,110,20],[660,350,110,20],[820,315,110,20],[660,250,90,16],[500,210,90,16]], coins:[[210,415],[370,380],[530,345],[690,310],[850,275],[680,220],[520,180]], enemies:[[180,425,100,2.6],[500,355,100,2.2]] },
  { platforms: [[0,500,960,40],[120,420,130,20],[300,370,130,20],[480,320,130,20],[660,270,130,20],[820,220,130,20],[280,260,90,16],[460,210,90,16]], coins:[[150,380],[330,330],[510,280],[690,230],[850,180],[305,230],[485,180]], enemies:[[300,340,110,2.4],[660,240,100,2.6]] },
  { platforms: [[0,500,960,40],[90,460,100,20],[230,420,100,20],[370,380,100,20],[510,340,100,20],[650,300,100,20],[790,260,100,20],[680,420,130,20]], coins:[[120,420],[260,380],[400,340],[540,300],[680,260],[820,220],[715,380]], enemies:[[520,310,90,2.8],[680,390,120,2.3]] },
  { platforms: [[0,500,960,40],[150,450,120,20],[310,400,120,20],[470,350,120,20],[630,300,120,20],[790,250,120,20],[390,260,100,16],[550,220,100,16]], coins:[[180,410],[340,360],[500,310],[660,260],[820,210],[420,230],[580,190]], enemies:[[150,420,100,2.8],[470,320,100,3.0],[790,220,100,2.2]] },
  { platforms: [[0,500,960,40],[120,460,90,20],[260,420,90,20],[400,380,90,20],[540,340,90,20],[680,300,90,20],[820,260,90,20],[540,250,90,16],[400,210,90,16]], coins:[[140,420],[280,380],[420,340],[560,300],[700,260],[840,220],[560,220],[420,180]], enemies:[[260,390,90,3.0],[540,310,90,3.2],[820,230,90,2.5]] }
];

function cloneLevel(base) {
  return {
    platforms: base.platforms.map(([x,y,w,h]) => ({x,y,w,h})),
    coins: base.coins.map(([x,y]) => ({x,y,collected:false})),
    enemies: base.enemies.map(([x,y,range,speed]) => ({x,y,w:30,h:28,startX:x,range,speed,dir:1})),
    goal: { x: 900, y: 200, w: 30, h: 300 },
  };
}

let currentLevel = cloneLevel(levelTemplates[levelIndex]);

function resetPlayer() { player.x = 70; player.y = 420; player.dx = 0; player.dy = 0; }
function loadLevel(idx) { levelIndex = idx; currentLevel = cloneLevel(levelTemplates[levelIndex]); levelTimer = 120; resetPlayer(); ui.message.textContent = `Nivel ${idx+1}`; }
function rectsOverlap(a,b) { return a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y; }

function update() {
  if (gameWon) return;

  const now = performance.now();
  if (now - lastTimerTick >= 1000) { levelTimer--; lastTimerTick = now; }
  if (levelTimer <= 0) loseLife('Se terminó el tiempo');

  const left = keys['ArrowLeft'] || keys['a'];
  const right = keys['ArrowRight'] || keys['d'];
  player.dx = left ? -player.speed : right ? player.speed : 0;
  if ((keys['ArrowUp'] || keys['w'] || keys[' ']) && player.grounded) {
    player.dy = player.jump;
    player.grounded = false;
  }

  player.dy += GRAVITY;
  player.x += player.dx;
  player.y += player.dy;

  if (player.x < 0) player.x = 0;
  if (player.x + player.w > canvas.width) player.x = canvas.width - player.w;

  player.grounded = false;
  for (const p of currentLevel.platforms) {
    if (rectsOverlap(player, p)) {
      const prevY = player.y - player.dy;
      if (prevY + player.h <= p.y + 2) {
        player.y = p.y - player.h;
        player.dy = 0;
        player.grounded = true;
      }
    }
  }

  if (player.y > canvas.height + 50) loseLife('Caíste al vacío');

  for (const c of currentLevel.coins) {
    if (!c.collected && rectsOverlap(player, {x:c.x,y:c.y,w:14,h:14})) {
      c.collected = true;
      player.coins += 1;
    }
  }

  for (const e of currentLevel.enemies) {
    e.x += e.speed * e.dir;
    if (e.x < e.startX - e.range || e.x > e.startX + e.range) e.dir *= -1;
    if (rectsOverlap(player, e)) loseLife('Te golpeó un enemigo');
  }

  if (rectsOverlap(player, currentLevel.goal)) {
    if (levelIndex === MAX_LEVELS - 1) {
      gameWon = true;
      ui.message.textContent = '¡Ganaste! Completaste los 10 niveles.';
    } else {
      loadLevel(levelIndex + 1);
    }
  }

  ui.level.textContent = String(levelIndex + 1);
  ui.lives.textContent = String(player.lives);
  ui.coins.textContent = String(player.coins);
  ui.timer.textContent = String(levelTimer);
}

function loseLife(reason) {
  player.lives -= 1;
  if (player.lives <= 0) {
    ui.message.textContent = `Game Over: ${reason}`;
    player.lives = 3;
    player.coins = 0;
    gameWon = false;
    loadLevel(0);
  } else {
    ui.message.textContent = `${reason}. Te quedan ${player.lives} vidas.`;
    resetPlayer();
  }
}

function draw() {
  ctx.clearRect(0,0,canvas.width,canvas.height);

  // montañas decorativas
  ctx.fillStyle = 'rgba(15,23,42,.25)';
  for (let i=0;i<5;i++) {
    ctx.beginPath();
    ctx.moveTo(i*220,500);
    ctx.lineTo(i*220+120,260);
    ctx.lineTo(i*220+240,500);
    ctx.fill();
  }

  for (const p of currentLevel.platforms) {
    ctx.fillStyle = '#92400e';
    ctx.fillRect(p.x,p.y,p.w,p.h);
    ctx.fillStyle = '#65a30d';
    ctx.fillRect(p.x,p.y,p.w,7);
  }

  for (const c of currentLevel.coins) {
    if (c.collected) continue;
    ctx.fillStyle = '#facc15';
    ctx.beginPath();
    ctx.arc(c.x+7,c.y+7,7,0,Math.PI*2);
    ctx.fill();
  }

  for (const e of currentLevel.enemies) {
    ctx.fillStyle = '#b91c1c';
    ctx.fillRect(e.x,e.y,e.w,e.h);
    ctx.fillStyle = '#111827';
    ctx.fillRect(e.x + 6, e.y + 9, 5, 5);
    ctx.fillRect(e.x + 19, e.y + 9, 5, 5);
  }

  const g = currentLevel.goal;
  ctx.fillStyle = '#f8fafc';
  ctx.fillRect(g.x, g.y, 4, g.h);
  ctx.fillStyle = '#22d3ee';
  ctx.fillRect(g.x + 4, g.y + 8, 26, 18);

  ctx.fillStyle = '#16a34a';
  ctx.fillRect(player.x, player.y, player.w, player.h);
  ctx.fillStyle = '#fde68a';
  ctx.fillRect(player.x + 8, player.y + 8, 18, 12);
}

function gameLoop() { update(); draw(); requestAnimationFrame(gameLoop); }

window.addEventListener('keydown', (e)=> keys[e.key] = true);
window.addEventListener('keyup', (e)=> keys[e.key] = false);
document.getElementById('restart').addEventListener('click', ()=> { player.lives = 3; player.coins = 0; gameWon = false; loadLevel(0); });
document.getElementById('next').addEventListener('click', ()=> { if (levelIndex < MAX_LEVELS - 1) loadLevel(levelIndex + 1); });

loadLevel(0);
gameLoop();
