#!/usr/bin/env node
/**
 * 生财有术 (scys-mcp) 本地 Stdio 桥接适配器
 * 负责 OAuth 2.1 + PKCE 动态授权、Token 本地缓存与自动刷新，
 * 以及将远程 Streamable HTTP / SSE MCP 转换为标准本地 Stdio MCP 服务。
 */

import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { execFile } from 'node:child_process';
import readline from 'node:readline';

const CREDENTIALS_FILE = path.join(
  process.env.HOME || '/tmp',
  '.gemini',
  'antigravity',
  'scys-credentials.json'
);

const DCR_ENDPOINT = 'https://mcp.scys.com/mcp-oauth/register';
const AUTH_ENDPOINT = 'https://mcp.scys.com/mcp-oauth/authorize';
const TOKEN_ENDPOINT = 'https://mcp.scys.com/mcp-oauth/token';
const MCP_ENDPOINT = 'https://mcp.scys.com/shengcai-web/mcp';
const REDIRECT_URI = 'http://127.0.0.1:3000/callback';
const PORT = 3000;

// 确保凭据存储目录存在
const credDir = path.dirname(CREDENTIALS_FILE);
if (!fs.existsSync(credDir)) {
  fs.mkdirSync(credDir, { recursive: true });
}

/** 读取已保存的凭据 */
function loadCredentials() {
  try {
    if (fs.existsSync(CREDENTIALS_FILE)) {
      const data = JSON.parse(fs.readFileSync(CREDENTIALS_FILE, 'utf8'));
      return data;
    }
  } catch (e) {
    // 忽略读取错误
  }
  return null;
}

/** 安全保存凭据（权限 0600） */
function saveCredentials(creds) {
  fs.writeFileSync(CREDENTIALS_FILE, JSON.stringify(creds, null, 2), {
    mode: 0o600,
  });
}

/** 动态客户端注册 (RFC 7591) */
async function registerClient() {
  const res = await fetch(DCR_ENDPOINT, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      client_name: 'scys-mcp',
      redirect_uris: [REDIRECT_URI],
      grant_types: ['authorization_code', 'refresh_token'],
      response_types: ['code'],
      token_endpoint_auth_method: 'none',
    }),
  });

  if (!res.ok) {
    throw new Error(`动态注册失败: HTTP ${res.status}`);
  }

  const data = await res.json();
  return data.client_id;
}

/** 生成 PKCE 参数 */
function generatePKCE() {
  const verifier = crypto.randomBytes(32).toString('base64url');
  const challenge = crypto
    .createHash('sha256')
    .update(verifier)
    .digest('base64url');
  return { verifier, challenge };
}

/** 刷新 Token */
async function refreshToken(clientId, refreshTokenStr) {
  const params = new URLSearchParams();
  params.set('grant_type', 'refresh_token');
  params.set('client_id', clientId);
  params.set('refresh_token', refreshTokenStr);
  params.set('resource', MCP_ENDPOINT);

  const res = await fetch(TOKEN_ENDPOINT, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: params.toString(),
  });

  if (!res.ok) {
    return null;
  }

  const tokenData = await res.json();
  const creds = {
    client_id: clientId,
    access_token: tokenData.access_token,
    refresh_token: tokenData.refresh_token || refreshTokenStr,
    expires_at: Date.now() + (tokenData.expires_in || 3600) * 1000 - 60000,
  };
  saveCredentials(creds);
  return creds.access_token;
}

/** 执行一次交互式 OAuth 2.1 + PKCE 授权 */
async function performOAuthLogin() {
  let creds = loadCredentials();
  let clientId = creds?.client_id;

  if (!clientId) {
    clientId = await registerClient();
  }

  const { verifier, challenge } = generatePKCE();
  const state = crypto.randomBytes(16).toString('base64url');

  return new Promise((resolve, reject) => {
    let resolved = false;

    const server = http.createServer(async (req, res) => {
      try {
        const reqUrl = new URL(req.url, `http://127.0.0.1:${PORT}`);
        if (reqUrl.pathname === '/callback') {
          const code = reqUrl.searchParams.get('code');
          const incomingState = reqUrl.searchParams.get('state');

          if (!code || incomingState !== state) {
            res.writeHead(400, { 'Content-Type': 'text/html; charset=utf-8' });
            res.end('<h1>授权失败：状态校验异常或未获得授权码</h1>');
            return;
          }

          // 向 Token 端点换取 Token
          const tokenParams = new URLSearchParams();
          tokenParams.set('grant_type', 'authorization_code');
          tokenParams.set('client_id', clientId);
          tokenParams.set('code', code);
          tokenParams.set('redirect_uri', REDIRECT_URI);
          tokenParams.set('code_verifier', verifier);
          tokenParams.set('resource', MCP_ENDPOINT);

          const tokenRes = await fetch(TOKEN_ENDPOINT, {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: tokenParams.toString(),
          });

          if (!tokenRes.ok) {
            const errText = await tokenRes.text();
            res.writeHead(500, { 'Content-Type': 'text/html; charset=utf-8' });
            res.end(`<h1>Token 换取失败</h1><pre>${errText}</pre>`);
            return;
          }

          const tokenData = await tokenRes.json();
          saveCredentials({
            client_id: clientId,
            access_token: tokenData.access_token,
            refresh_token: tokenData.refresh_token,
            expires_at:
              Date.now() + (tokenData.expires_in || 3600) * 1000 - 60000,
          });

          res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
          res.end(`
            <html>
              <head><title>生财有术 MCP 授权成功</title></head>
              <body style="font-family: -apple-system, sans-serif; text-align: center; padding-top: 60px;">
                <h1 style="color: #10b981;">✓ 授权成功！</h1>
                <p style="color: #4b5563; font-size: 16px;">已成功获取生财有术 MCP 访问凭据，您可以直接关闭此页面返回 IDE。</p>
              </body>
            </html>
          `);

          if (!resolved) {
            resolved = true;
            server.close();
            resolve(tokenData.access_token);
          }
        } else {
          res.writeHead(404);
          res.end();
        }
      } catch (err) {
        if (!resolved) {
          resolved = true;
          server.close();
          reject(err);
        }
      }
    });

    server.listen(PORT, '127.0.0.1', () => {
      const authUrl = `${AUTH_ENDPOINT}?response_type=code&client_id=${clientId}&redirect_uri=${encodeURIComponent(
        REDIRECT_URI
      )}&scope=mcp&code_challenge=${challenge}&code_challenge_method=S256&state=${state}&resource=${encodeURIComponent(
        MCP_ENDPOINT
      )}`;

      // 使用原生 open 命令拉起浏览器
      execFile('/usr/bin/open', [authUrl], (err) => {
        if (err) {
          console.error('拉起浏览器失败，请手动打开授权链接');
        }
      });
    });

    // 5 分钟超时处理
    setTimeout(() => {
      if (!resolved) {
        resolved = true;
        server.close();
        reject(new Error('授权超时（5分钟未接收到回调）'));
      }
    }, 300000);
  });
}

/** 获取有效 Access Token（自动使用缓存或刷新） */
async function getValidAccessToken() {
  const creds = loadCredentials();
  if (!creds || !creds.access_token) {
    return await performOAuthLogin();
  }

  // 若 Token 未过期，直接返回
  if (creds.expires_at && Date.now() < creds.expires_at) {
    return creds.access_token;
  }

  // 若已过期，尝试使用 refresh_token 刷新
  if (creds.refresh_token && creds.client_id) {
    const refreshed = await refreshToken(creds.client_id, creds.refresh_token);
    if (refreshed) {
      return refreshed;
    }
  }

  // 刷新失败则重新登录
  return await performOAuthLogin();
}

/** 转发请求到生财有术远程 MCP */
async function forwardMcpRequest(token, jsonRpcPayload) {
  // 支持 Streamable HTTP 规范请求
  const res = await fetch(MCP_ENDPOINT, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json, text/event-stream',
      'Authorization': `Bearer ${token}`,
    },
    body: JSON.stringify(jsonRpcPayload),
  });

  if (!res.ok) {
    // 处理可能得 401 并重试一次
    if (res.status === 401) {
      const creds = loadCredentials();
      if (creds?.refresh_token && creds?.client_id) {
        const refreshed = await refreshToken(
          creds.client_id,
          creds.refresh_token
        );
        if (refreshed) {
          return forwardMcpRequest(refreshed, jsonRpcPayload);
        }
      }
    }
    const errText = await res.text();
    throw new Error(`远程端点返回 HTTP ${res.status}: ${errText}`);
  }

  const contentType = res.headers.get('content-type') || '';
  if (contentType.includes('application/json')) {
    return await res.json();
  } else if (contentType.includes('text/event-stream')) {
    // 解析 SSE 响应中的首个完整事件
    const bodyText = await res.text();
    const match = bodyText.match(/data:\s*(\{.*\})/);
    if (match) {
      return JSON.parse(match[1]);
    }
    throw new Error(`无法解析 SSE 响应: ${bodyText.slice(0, 200)}`);
  } else {
    const text = await res.text();
    return JSON.parse(text);
  }
}

/** 运行交互式命令行测试 / 工具验证 */
async function runTest() {
  const token = await getValidAccessToken();
  console.log('[scys-mcp] 成功获取有效访问凭据。');

  // 1. 发送 initialize 初始化请求
  console.log('[scys-mcp] 正在初始化远程 MCP 连接...');
  const initRes = await forwardMcpRequest(token, {
    jsonrpc: '2.0',
    id: 1,
    method: 'initialize',
    params: {
      protocolVersion: '2024-11-05',
      capabilities: {},
      clientInfo: { name: 'scys-bridge', version: '1.0.0' },
    },
  });
  console.log('[scys-mcp] 初始化成功，服务端信息:', initRes.result?.serverInfo?.name || 'scys');

  // 2. 发送 tools/list 查询所有可用工具
  console.log('[scys-mcp] 正在获取工具列表...');
  const toolsRes = await forwardMcpRequest(token, {
    jsonrpc: '2.0',
    id: 2,
    method: 'tools/list',
    params: {},
  });

  const tools = toolsRes.result?.tools || [];
  console.log(`[scys-mcp] 获取到 ${tools.length} 个可用工具:`);
  for (const t of tools) {
    console.log(` - ${t.name}: ${t.description?.slice(0, 60) || ''}`);
  }

  // 3. 执行一个只读调用验证
  if (tools.length > 0) {
    const readOnlyTool = tools[0].name;
    console.log(`[scys-mcp] 执行只读验证调用: ${readOnlyTool}...`);
    try {
      const callRes = await forwardMcpRequest(token, {
        jsonrpc: '2.0',
        id: 3,
        method: 'tools/call',
        params: {
          name: readOnlyTool,
          arguments: {},
        },
      });
      console.log('[scys-mcp] 只读调用响应状态: 成功');
      return { tools, readOnlyTool, result: callRes.result };
    } catch (e) {
      console.log('[scys-mcp] 只读调用响应:', e.message);
      return { tools, readOnlyTool, error: e.message };
    }
  }

  return { tools };
}

/** 作为标准 Stdio Server 运行 */
async function runStdioServer() {
  let token;
  try {
    token = await getValidAccessToken();
  } catch (err) {
    process.stderr.write(`[scys-mcp] 授权失败: ${err.message}\n`);
    process.exit(1);
  }

  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
    terminal: false,
  });

  rl.on('line', async (line) => {
    const trimmed = line.trim();
    if (!trimmed) return;

    let req;
    try {
      req = JSON.parse(trimmed);
    } catch (err) {
      return;
    }

    // 处理通知类型（无需响应）
    if (!req.id && req.method?.startsWith('notifications/')) {
      return;
    }

    try {
      // 代理转发给远程 MCP
      const remoteRes = await forwardMcpRequest(token, req);
      process.stdout.write(JSON.stringify(remoteRes) + '\n');
    } catch (err) {
      const errRes = {
        jsonrpc: '2.0',
        id: req.id,
        error: {
          code: -32603,
          message: err.message,
        },
      };
      process.stdout.write(JSON.stringify(errRes) + '\n');
    }
  });
}

// 主入口
const mode = process.argv[2];
if (mode === '--login') {
  performOAuthLogin()
    .then(() => {
      console.log('OAuth 授权流程完成，凭据已安全保存。');
      process.exit(0);
    })
    .catch((err) => {
      console.error('OAuth 授权流程出错:', err.message);
      process.exit(1);
    });
} else if (mode === '--test') {
  runTest()
    .then(() => process.exit(0))
    .catch((err) => {
      console.error('测试运行失败:', err.message);
      process.exit(1);
    });
} else {
  runStdioServer();
}
