const USER_AGENT =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " +
  "(KHTML, like Gecko) Chrome/100.0.0.0 Safari/537.36";

const ALLOWED_HOSTS = new Set(["mp.weixin.qq.com"]);

function textResponse(message, status = 400) {
  return new Response(message, {
    status,
    headers: {
      "Content-Type": "text/plain; charset=utf-8",
    },
  });
}

function validateTarget(rawUrl) {
  if (!rawUrl) {
    throw new Error("缺少 url 参数");
  }

  const target = new URL(rawUrl);
  if (!["http:", "https:"].includes(target.protocol)) {
    throw new Error("只支持 HTTP/HTTPS URL");
  }
  if (!ALLOWED_HOSTS.has(target.hostname)) {
    throw new Error(`不允许代理该域名：${target.hostname}`);
  }

  return target;
}

function validateAuthorization(requestUrl, env) {
  const token = env.WECHAT_PROXY_TOKEN || "";
  if (!token) {
    return;
  }

  const provided = requestUrl.searchParams.get("authorization") || "";
  if (provided !== token) {
    throw new Error("代理 token 不正确");
  }
}

export default {
  async fetch(request, env) {
    if (request.method !== "GET") {
      return textResponse("只支持 GET 请求", 405);
    }

    try {
      const requestUrl = new URL(request.url);
      validateAuthorization(requestUrl, env);
      const target = validateTarget(requestUrl.searchParams.get("url"));

      const response = await fetch(target.toString(), {
        method: "GET",
        headers: {
          "User-Agent": USER_AGENT,
          Referer: "https://mp.weixin.qq.com/",
        },
        redirect: "follow",
      });

      return new Response(response.body, {
        status: response.status,
        statusText: response.statusText,
        headers: {
          "Access-Control-Allow-Origin": "*",
          "Content-Type": response.headers.get("Content-Type") || "text/html; charset=utf-8",
        },
      });
    } catch (error) {
      return textResponse(error instanceof Error ? error.message : String(error), 400);
    }
  },
};
