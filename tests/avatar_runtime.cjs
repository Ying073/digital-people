const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

let now = 0, timerId = 0;
const timers = new Map();
const elements = new Map();
const storage = new Map([['xixi-sound', 'off']]);
function element(id) {
  if (!elements.has(id)) elements.set(id, {
    dataset: {}, style: { setProperty(name, value) { this[name] = value; } }, children: [],
    classList: { add() {}, remove() {} }, setAttribute(name, value) { this[name] = String(value); },
    setPointerCapture() {}, releasePointerCapture() {}, hasPointerCapture: () => true,
    naturalWidth: 640, naturalHeight: 740, clientWidth: 200, clientHeight: 300,
    decode: async () => {},
    getContext: () => ({ clearRect() {}, save() {}, restore() {}, translate() {}, transform() {}, setTransform() {}, drawImage() {} }),
  });
  return elements.get(id);
}
element('faceOverlay').children = Array.from({length: 7}, () => ({style: {}}));
const context = vm.createContext({
  console, Map, Math, Date: { now: () => now },
  localStorage: { getItem: (key) => storage.get(key) ?? null, setItem: (key, value) => storage.set(key, String(value)) },
  window: { matchMedia: () => ({matches: false}) },
  document: { visibilityState: 'visible', getElementById: element },
  Audio: class { paused = true; }, ResizeObserver: class { observe() {} },
  Image: class { decode = async () => {}; },
  setTimeout(fn, delay) { timers.set(++timerId, {fn, at: now + delay, delay}); return timerId; },
  clearTimeout(id) { timers.delete(id); },
  requestAnimationFrame(fn) {
    if (fn.name !== 'tick') { fn(); return; }
    timers.set(++timerId, {fn, at: now + 10, delay: 10}); return timerId;
  },
  cancelAnimationFrame(id) { timers.delete(id); },
});
const source = fs.readFileSync('app/static/app.js', 'utf8').split('const languageAliases =')[0];
vm.runInContext(source, context);
const run = (code) => vm.runInContext(code, context);
async function settle() { for (let i=0; i<10; i++) await Promise.resolve(); }
async function advance(ms) {
  const end = now + ms;
  while (true) {
    const next = [...timers].filter(([,t]) => t.at <= end).sort((a,b) => a[1].at-b[1].at)[0];
    if (!next) break;
    now = next[1].at; timers.delete(next[0]); next[1].fn(); await settle();
  }
  now = end;
}

(async () => {
  let shift = 0;
  const box = (left, top, width, height) => ({left, top, width, height, right:left+width, bottom:top+height});
  element('avatarStage').getBoundingClientRect = () => box(0, 0, 500, 700);
  element('workspace').getBoundingClientRect = () => box(0, 0, 1200, 700);
  element('courseRail').getBoundingClientRect = () => box(0, 0, 220, 700);
  element('workspaceResizer').getBoundingClientRect = () => box(720, 0, 8, 700);
  element('avatarWrap').getBoundingClientRect = () => box(20+shift, 350, 360, 340);
  for (const id of ['avatarImage', 'avatarImageNext']) {
    element(id).getBoundingClientRect = () => box(35+shift, 350, 280, 324);
  }
  element('speechBubble').offsetWidth = 140;
  element('speechBubble').offsetHeight = 62;
  context.document.querySelector = () => ({getBoundingClientRect: () => box(35, 35, 430, 308)});
  assert.equal(run('clampStagePanelWidth(100, {min: 300, max: 592})'), 300);
  assert.equal(run('clampStagePanelWidth(900, {min: 300, max: 592})'), 592);
  run('beginWorkspaceResize({pointerId: 3, button: 0, clientX: 600, preventDefault() {}})');
  run('moveWorkspaceResize({pointerId: 3, clientX: 700, preventDefault() {}})');
  assert.equal(element('workspace').style['--stage-panel-width'], '592px', 'divider keeps enough room for chat');
  run('endWorkspaceResize({pointerId: 3})');
  assert.equal(storage.get('xixi-stage-width'), '592', 'released divider width persists');
  assert.equal(element('workspaceResizer')['aria-valuenow'], '592');
  run('followSpeechBubble()');
  const bubbleLeft = parseFloat(element('speechBubble').style.left);
  shift = 40;
  run('followSpeechBubble()');
  assert.equal(parseFloat(element('speechBubble').style.left), bubbleLeft, 'same local anchor means bubble travels exactly with avatar');
  shift = 240;
  run('followSpeechBubble()');
  assert.equal(element('speechBubble').dataset.side, 'left', 'bubble switches sides near right stage edge');
  assert.ok(parseFloat(element('speechBubble').style.top) + 350 >= 351, 'bubble clears board');
  shift = 0;
  const completeText = 'C++是给电脑下命令的语言，能让电脑帮你算数、整理数据和画图。后面的内容也要完整显示。';
  const pages = run(`bubblePages(${JSON.stringify(completeText)})`);
  assert.equal(pages.join(''), completeText, 'paging must preserve every character');
  assert.ok(pages.every(page => Array.from(page).length <= 20));
  run(`showBubble(${JSON.stringify(completeText)})`);
  for (let i = 0; i < pages.length; i++) {
    assert.equal(element('speechBubble').textContent, pages[i]);
    await advance(Math.max(2200, Array.from(pages[i]).length * 220));
  }
  assert.equal(element('speechBubble').textContent, pages.at(-1), 'keep the final page');
  run(`showBubble(${JSON.stringify(completeText)}); showBubble("新的提示。");`);
  await advance(5000);
  assert.equal(element('speechBubble').textContent, '新的提示。', 'cancel obsolete pages');
  run('idleOffsetX = 0; avatarOffsetY = 0; applyAvatarOffset()');
  const clamped = run('clampAvatarOffset(999, -999, {minX: -30, maxX: 160, minY: -220, maxY: 8})');
  assert.deepEqual({x: clamped.x, y: clamped.y}, {x: 160, y: -220}, 'dragging stays inside the stage');
  run('beginAvatarDrag({pointerId: 7, button: 0, clientX: 100, clientY: 500, preventDefault() {}})');
  assert.equal(element('avatarWrap').dataset.dragging, 'true');
  run('moveAvatarDrag({pointerId: 7, clientX: 220, clientY: 400, preventDefault() {}})');
  assert.equal(element('avatarStage').style['--avatar-offset-x'], '120px');
  assert.equal(element('avatarStage').style['--avatar-offset-y'], '-100px');
  assert.equal(element('avatarWrap').style['--avatar-drag-tilt'], '4deg', 'body leans gently toward movement');
  run('endAvatarDrag({pointerId: 7})');
  assert.equal(element('avatarWrap').dataset.dragging, 'false');
  assert.equal(run('dragState'), null);
  assert.equal(run('idleOffsetX'), 120, 'released position stays where the learner placed it');
  assert.equal(run('avatarOffsetY'), -100);
  run('beginAvatarAttention({clientX: 40})');
  run('trackAvatarAttention({clientX: 300, clientY: 350})');
  assert.equal(element('avatarWrap').dataset.attentive, 'true', 'avatar notices a nearby pointer');
  assert.equal(element('avatarWrap').style['--avatar-attention-tilt'], '0.8deg');
  const depthTilt = run('depthTiltForPointer(300, 350, {left: 35, top: 350, width: 280, height: 324})');
  assert.equal(depthTilt.x, 1.6, 'pointer above the head adds a subtle bounded forward tilt');
  assert.ok(depthTilt.y > 1.9 && depthTilt.y <= 2.2, 'horizontal pointer position adds a subtle bounded side turn');
  assert.equal(element('avatarWrap').style['--avatar-depth-tilt-x'], '1.6deg');
  assert.equal(element('avatarWrap').style['--avatar-depth-tilt-y'], `${depthTilt.y}deg`);
  run('clearAvatarAttention()');
  assert.equal(element('avatarWrap').dataset.attentive, 'false');
  assert.equal(element('avatarWrap').style['--avatar-depth-tilt-x'], '0deg');
  assert.equal(element('avatarWrap').style['--avatar-depth-tilt-y'], '0deg');
  run('beginAvatarDrag({pointerId: 8, button: 0, clientX: 150, clientY: 500, preventDefault() {}})');
  run('endAvatarDrag({pointerId: 8})');
  assert.equal(element('avatarWrap').dataset.teacherReaction, 'acknowledge', 'a tap gets a calm teacher acknowledgment');
  await advance(820);
  assert.equal(element('avatarWrap').dataset.teacherReaction, 'none');
  run('idleOffsetX = 0; avatarOffsetY = 0; applyAvatarOffset()');
  run('facePatch = () => "data:image/png;base64,test"; cleanedAvatar = async src => src; drawGait = () => {};');
  run('scheduleIdle()');
  for (let i=0; i<6; i++) {
    const delay = timers.get(run('idleDelayTimer'));
    assert.ok(delay.delay >= 14000 && delay.delay <= 24000, 'teacher gestures leave calm space between movements');
    await advance(delay.at - now);
    assert.notEqual(element('avatarWrap').dataset.idleAction, 'none');
    assert.ok(['glance', 'posture', 'nod'].includes(element('avatarWrap').dataset.idleAction));
    assert.notEqual(element('avatarWrap').dataset.gait, 'true', 'teacher does not roam autonomously');
    const action = timers.get(run('idleActionTimer'));
    await advance(action.at - now);
    assert.equal(element('avatarWrap').dataset.idleAction, 'none');
  }
  run('cancelIdleMotion(); scheduleBlink()');
  const blink = timers.get(run('blinkTimer'));
  assert.ok(blink.delay >= 2800 && blink.delay <= 7600);
  await advance(blink.at-now);
  assert.equal(element('avatarWrap').dataset.blinking, 'true');
  run('setAvatar("wave")'); await settle(); await advance(100);
  assert.equal(element('avatarWrap').dataset.blinking, 'false');
  assert.ok(timers.has(run('blinkTimer')), 'switching during a blink must not stop future blinks');
  run('setTalking(true)');
  assert.equal(element('avatarWrap').dataset.idleAction, 'none');
  assert.equal(timers.has(run('idleDelayTimer')), false);
  assert.equal(timers.has(run('idleActionTimer')), false);
  assert.equal(element('avatarWrap').dataset.expression, 'explaining', 'talking uses an animated explaining expression');
  run('setTalking(false)');
  assert.equal(run('isKeyKnowledgeSegment("变量像一个有名字的小盒子。")'), false);
  assert.equal(run('isKeyKnowledgeSegment("注意，= 是赋值，== 才是比较相等。")'), true);
  assert.equal(run('isKeyKnowledgeSegment("这里非常关键，一定要先判断边界。")'), true);
  const emphasisSegments = run('speechEmphasisSegments("先认识变量。注意这里必须使用两个等号。然后继续练习。")');
  assert.deepEqual([...emphasisSegments], ['先认识变量。', '注意这里必须使用两个等号。', '然后继续练习。']);
  const emphasizedSegment = run('speechSegmentAtProgress(["先认识变量。", "注意这里必须使用两个等号。", "然后继续练习。"], .5)');
  assert.equal(emphasizedSegment, '注意这里必须使用两个等号。');
  run('setTalking(true, "注意，这个区别很容易写错。")');
  assert.equal(element('avatarWrap').dataset.knowledgeEmphasis, 'true');
  assert.equal(element('avatarWrap').dataset.expression, 'emphasis', 'key knowledge briefly tightens the teacher expression');
  run('setKnowledgeEmphasis(false)');
  assert.equal(element('avatarWrap').dataset.expression, 'explaining', 'ordinary explanation restores the natural expression');
  run('setTalking(false)');
  assert.equal(element('avatarWrap').dataset.knowledgeEmphasis, 'false');
  for (const [pose, expected, expression] of [
    ['idle','idle','neutral'], ['wave','wave','warm'], ['thinking','think','curious'],
    ['explain','explain','explaining'], ['point','point','focused'], ['read','read','focused'],
    ['encourage','wave','warm'], ['correct','think','concerned'],
    ['celebrate','wave','celebrate'], ['speaking','explain','explaining'],
  ]) {
    run(`setAvatar('${pose}')`); await settle(); await advance(100);
    assert.equal(element('faceOverlay').dataset.pose, expected);
    assert.equal(element('avatarWrap').dataset.expression, expression, `${pose} maps to its teacher expression`);
    assert.equal(element('faceOverlay').dataset.ready, 'true');
    assert.equal(element('faceOverlay').children[3].style.backgroundImage, 'none', 'expressive brows never cover the face with a raster patch');
    assert.equal(element('faceOverlay').children[4].style.backgroundImage, 'none', 'both brows remain transparent overlays');
    assert.equal(element('avatarWrap').dataset.transitioning, 'false');
  }
  run('setAvatar("idle"); setAvatar("wave"); setAvatar("read")');
  await settle(); await advance(200);
  assert.equal(element('faceOverlay').dataset.pose, 'read', 'latest requested frame owns landmarks');
  for (const [width,height] of [[200,300],[300,200],[120,90]]) {
    const image = run('avatarFrames[activeAvatarFrame]');
    image.clientWidth=width; image.clientHeight=height; run('alignFaceOverlay()');
    const style=element('faceOverlay').style, scale=Math.min(width/640,height/740);
    assert.equal(parseFloat(style.width),640*scale);
    assert.equal(parseFloat(style.height),740*scale);
    assert.equal(parseFloat(style.left),(width-640*scale)/2);
    assert.equal(parseFloat(style.top),height-740*scale);
  }
  run('document.visibilityState="hidden"; cancelIdleMotion(); scheduleBlink(); scheduleIdle()');
  assert.equal(timers.has(run('blinkTimer')), false);
  assert.equal(timers.has(run('idleDelayTimer')), false);
  run('document.visibilityState="visible"; reducedMotion.matches=true; scheduleBlink(); scheduleIdle()');
  assert.equal(timers.has(run('blinkTimer')), false);
  assert.equal(timers.has(run('idleDelayTimer')), false);
  console.log('PASS: draggable young-teacher attention, calm tap acknowledgment, restrained idle gestures, blinks, cancellation, poses, contain geometry, hidden/reduced motion');
})().catch(error => { console.error(error); process.exitCode=1; });
