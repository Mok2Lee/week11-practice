'use strict';

const config = window.DRIVE_CONFIG ?? {};
const $ = id => document.getElementById(id);
let accessToken;
let nextPage;

function status(message, error = false) {
  $('status').textContent = message;
  $('status').dataset.error = String(error);
}

function signOut() {
  accessToken = undefined;
  $('access-form').reset();
  $('files').replaceChildren();
  $('rate-result').textContent = '';
  $('drive').hidden = true;
  $('sign-out').hidden = true;
  $('access').hidden = false;
  status('팀 실습 코드를 입력하세요.');
}

function api(path, {method = 'GET', body} = {}) {
  const headers = {Authorization:`Bearer ${accessToken}`};
  if (body) headers['Content-Type'] = 'application/json';
  return fetch(`${config.apiBase.replace(/\/$/, '')}${path}`, {method, headers, cache:'no-store', body});
}

async function payload(response) {
  const data = await response.json().catch(() => ({}));
  if (response.status === 401) throw new Error('팀 실습 코드를 확인하세요.');
  if (response.status === 429) throw new Error('429 요청이 몰렸습니다. 잠시 뒤 다시 시도하세요.');
  if (!response.ok) throw new Error(data.message || `요청 오류 ${response.status}`);
  return data;
}

function fileRow(file) {
  const row = document.createElement('li');
  const detail = document.createElement('span');
  detail.textContent = `${file.name} · ${file.size.toLocaleString('ko-KR')} B`;
  const button = document.createElement('button');
  button.textContent = '다운로드';
  button.type = 'button';
  button.setAttribute('aria-label', `${file.name} 다운로드`);
  button.addEventListener('click', () => perform(button, () => download(file)));
  row.append(detail, button);
  return row;
}

async function loadFiles(append = false) {
  const query = append && nextPage ? `?${new URLSearchParams({page:nextPage})}` : '';
  const data = await payload(await api(`/files${query}`));
  if (!append) $('files').replaceChildren();
  $('files').append(...data.files.map(fileRow));
  nextPage = data.nextPage;
  $('next-page').hidden = !nextPage;
  status(`목록 조회 200 · 이 페이지의 파일 ${data.files.length}개`);
}

async function upload(file) {
  const ticket = await payload(await api('/files/upload-url', {
    method:'POST', body:JSON.stringify({name:file.name, size:file.size}),
  }));
  const response = await fetch(ticket.url,{method:'PUT',headers:ticket.headers,body:file});
  if (!response.ok) throw new Error(`S3 업로드 오류 ${response.status}`);
  status(`S3 업로드 ${response.status} · ${file.name} · 목록 조회로 확인`);
  $('upload-form').reset();
}

async function download(file) {
  const ticket = await payload(await api(`/files/${encodeURIComponent(file.id)}/download-url`));
  const link = document.createElement('a');
  link.href = ticket.url;
  link.rel = 'noreferrer';
  link.click();
  status(`다운로드 요청 · ${file.name} · 브라우저 다운로드에서 파일 확인`);
}

async function burst() {
  const id = Date.now();
  $('rate-result').textContent = 'GET /files 24건 요청 중';
  const results = await Promise.all(Array.from({length:24}, (_, index) => api(`/files?probe=${id}-${index}`)
    .then(res => String(res.status)).catch(() => '브라우저 확인 필요')));
  const count = code => results.filter(result => result === code).length;
  const other = results.length - count('200') - count('429');
  $('rate-result').textContent = `200 성공 ${count('200')}건 · 429 요청량 초과 ${count('429')}건`
    + (other ? ` · 기타 응답 ${other}건` : '');
}

async function perform(button, operation) {
  button.disabled = true;
  try { await operation(); }
  catch (error) { status(error.message || '요청 중 오류가 발생했습니다.', true); }
  finally { button.disabled = false; }
}

function start() {
  if (!config.apiBase) {
    status('config.js에 API 주소를 입력하세요.', true);
    return;
  }
  $('access').hidden = false;
  status('팀 실습 코드를 입력하세요.');
  $('access-form').addEventListener('submit', event => {
    event.preventDefault();
    perform($('sign-in'), async () => {
      accessToken = $('team-code').value;
      await loadFiles();
      $('access-form').reset();
      $('access').hidden = true;
      $('sign-out').hidden = false;
      $('drive').hidden = false;
    });
  });
  $('sign-out').addEventListener('click', signOut);
  $('refresh').addEventListener('click', () => perform($('refresh'), loadFiles));
  $('next-page').addEventListener('click', () => perform($('next-page'), () => loadFiles(true)));
  $('burst').addEventListener('click', () => perform($('burst'), burst));
  $('upload-form').addEventListener('submit', event => {
    event.preventDefault();
    const file = $('file').files[0];
    if (file) perform($('upload'), () => upload(file));
  });

}

start();
