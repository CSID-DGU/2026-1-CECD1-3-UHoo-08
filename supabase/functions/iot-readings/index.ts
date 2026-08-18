// 화담 CARE — IoT 센서 수집 (Supabase Edge Function)
//
// ESP32 노드가 직접 호출한다. Python 쪽 AI/api/iot/router.py와 동일한 계약을 갖는다.
// 로직이 두 언어로 갈라지므로, 한쪽을 고치면 반드시 다른 쪽도 맞출 것.
//
// 배포 이유:
//     전체 AI 서버는 bge-m3(2.3GB) 때문에 상시 호스팅 비용이 크다.
//     수집 경로만 Edge Function으로 떼면 무료 한도(월 50만 회) 안에서 상시 운영된다.
//     노드 4대 × 10분 주기 = 월 17,280회로 한도의 3.5% 수준이다.
//
// 중복 수신:
//     (node_id, ts) 유니크 인덱스(012)를 전제로 upsert-ignore.
//     ESP32가 Wi-Fi 복구 후 버퍼를 재전송해도 멱등하다.
//
// 엔드포인트:
//     GET  /functions/v1/iot-readings/ping    펌웨어 브링업용 연결 확인
//     POST /functions/v1/iot-readings         측정값 적재 (단건·배치 공용)

import { createClient } from "jsr:@supabase/supabase-js@2";

// NTP 미동기 시 ESP32는 1970년 근처 시각을 붙인다.
// 열이력 적산(t_eff = Σ AF(T) × Δt)이 통째로 망가지므로 수집 단계에서 잘라낸다.
const MIN_TS = Date.parse("2020-01-01T00:00:00Z");
const MAX_BATCH = 288; // 10분 주기 × 2일치

const IOT_API_KEY = Deno.env.get("IOT_API_KEY") ?? "";

const sb = createClient(
  Deno.env.get("SUPABASE_URL")!,
  Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
);

type Reading = {
  ts: string;
  temperature?: number | null;
  humidity?: number | null;
  pm25?: number | null;
  gas_resistance?: number | null;
};

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

/** 센서 이상값 차단. 배선 불량 시 터무니없는 값이 들어오는 것을 막는다. */
function inRange(v: unknown, lo: number, hi: number, label: string): number | null {
  if (v === null || v === undefined) return null;
  const n = Number(v);
  if (!Number.isFinite(n) || n < lo || n > hi) {
    throw new Error(`${label} 값이 허용 범위(${lo}~${hi})를 벗어났습니다: ${v}`);
  }
  return n;
}

Deno.serve(async (req) => {
  const url = new URL(req.url);

  if (req.method === "GET" && url.pathname.endsWith("/ping")) {
    return json({ status: "ok", server_time: new Date().toISOString() });
  }

  if (req.method !== "POST") {
    return json({ detail: "POST만 허용됩니다" }, 405);
  }

  if (IOT_API_KEY && req.headers.get("X-Node-Key") !== IOT_API_KEY) {
    return json({ detail: "유효하지 않은 노드 키" }, 401);
  }

  let body: { node_id?: string; readings?: Reading[] };
  try {
    body = await req.json();
  } catch {
    return json({ detail: "JSON 파싱 실패" }, 400);
  }

  const nodeId = body.node_id;
  const readings = body.readings;

  if (!nodeId || !Array.isArray(readings) || readings.length === 0) {
    return json({ detail: "node_id와 readings(비어있지 않은 배열)가 필요합니다" }, 422);
  }
  if (readings.length > MAX_BATCH) {
    return json({ detail: `배치 최대 ${MAX_BATCH}건. 나눠서 전송하세요.` }, 413);
  }

  // 미등록 노드는 FK가 어차피 막지만, 404로 명시해야 현장에서 원인을 즉시 안다
  const { data: node, error: nodeErr } = await sb
    .from("iot_nodes")
    .select("node_id, node_type")
    .eq("node_id", nodeId)
    .maybeSingle();

  if (nodeErr) {
    return json({ detail: `노드 조회 실패: ${nodeErr.message}` }, 500);
  }
  if (!node) {
    return json(
      { detail: `미등록 노드입니다: ${nodeId}. iot_nodes에 먼저 등록하세요.` },
      404,
    );
  }

  let rows;
  try {
    rows = readings.map((r) => {
      const t = Date.parse(r.ts);
      if (Number.isNaN(t)) {
        throw new Error(`ts 파싱 실패: ${r.ts}`);
      }
      if (t < MIN_TS) {
        throw new Error("NTP 미동기 의심 시각. 노드의 시각 동기화를 확인하세요.");
      }
      return {
        node_id: nodeId,
        ts: new Date(t).toISOString(),
        temperature: inRange(r.temperature, -40, 125, "temperature"),
        humidity: inRange(r.humidity, 0, 100, "humidity"),
        pm25: inRange(r.pm25, 0, 1000, "pm25"),
        gas_resistance: inRange(r.gas_resistance, 0, 1e7, "gas_resistance"),
      };
    });
  } catch (e) {
    return json({ detail: (e as Error).message }, 422);
  }

  const { data, error } = await sb
    .from("sensor_readings")
    .upsert(rows, { onConflict: "node_id,ts", ignoreDuplicates: true })
    .select("id");

  if (error) {
    return json({ detail: `적재 실패: ${error.message}` }, 500);
  }

  const inserted = data?.length ?? 0;
  return json({
    node_id: nodeId,
    node_type: node.node_type,
    received: rows.length,
    inserted,
    duplicates: rows.length - inserted,
  });
});