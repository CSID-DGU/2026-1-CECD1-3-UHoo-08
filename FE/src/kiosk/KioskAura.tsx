import { useEffect, useRef, useState } from "react";
import { Renderer, Program, Mesh, Color, Triangle } from "ogl";

/**
 * 상태에 따라 색이 변하는 배경.
 *
 * 원본은 reactbits의 Iridescence다. 키오스크에 그대로 쓰면 안 되는 곳이
 * 있어 다섯 군데를 고쳤다.
 *
 *   색 변경    useEffect 의존성에 color가 있어 색이 바뀔 때마다 WebGL
 *              컨텍스트를 통째로 다시 만들었다. 깜빡이고, 몇 시간 켜두는
 *              화면에서는 컨텍스트가 샌다. uniform만 갱신하고 목표 색으로
 *              보간한다.
 *   입력       mousemove는 아이패드에 오지 않는다. 뺐다.
 *   프레임     60fps로 화면 전체를 다시 그리면 발열이 는다. 30fps로 묶었다.
 *   해상도     DPR 1 고정이었다. 아이패드는 2이고 KioskFrame이 1.17배 더
 *              확대하므로 경계가 뭉갠다. dpr로 빼서 실측으로 정한다.
 *   손실 대비  iOS 사파리는 메모리가 모자라면 컨텍스트를 회수한다. 시연
 *              중에 그러면 배경이 죽는다. CSS 그라데이션으로 떨어진다.
 *
 * 색 자체의 의미는 여기서 정하지 않는다. lib/auraState.ts가 정한다.
 */

const vertexShader = `
attribute vec2 uv;
attribute vec2 position;
varying vec2 vUv;
void main() {
  vUv = uv;
  gl_Position = vec4(position, 0, 1);
}
`;

const fragmentShader = `
precision highp float;
uniform float uTime;
uniform vec3 uColor;
uniform vec3 uResolution;
uniform float uSpeed;
varying vec2 vUv;
void main() {
  float mr = min(uResolution.x, uResolution.y);
  vec2 uv = (vUv.xy * 2.0 - 1.0) * uResolution.xy / mr;
  float d = -uTime * 0.5 * uSpeed;
  float a = 0.0;
  for (float i = 0.0; i < 8.0; ++i) {
    a += cos(i - d - a * uv.x);
    d += sin(uv.y * i + a);
  }
  d += uTime * 0.5 * uSpeed;
  vec3 col = vec3(cos(uv * vec2(d, a)) * 0.6 + 0.4, cos(a + d) * 0.5 + 0.5);
  col = cos(col * cos(vec3(d, a, 2.5)) * 0.5 + 0.5) * uColor;
  gl_FragColor = vec4(col, 1.0);
}
`;

/** 목표 색까지 가는 데 걸리는 대략의 시간(초). 뚝 끊기면 상태가 튄 것처럼 보인다. */
const COLOR_TAU_S = 0.9;

/** 30fps. 매 프레임 화면 전체를 다시 그리는 셰이더라 상한을 둔다. */
const FRAME_MS = 1000 / 30;

/** 첫 프레임 전 흰 화면이 번쩍이지 않도록 레터박스색으로 지운다. */
const CLEAR = [0x2a / 255, 0x2d / 255, 0x33 / 255] as const;

type Props = {
  /** 0~1 RGB. 바뀌면 부드럽게 넘어간다. */
  color: readonly [number, number, number];
  /** WebGL을 못 쓰게 됐을 때 대신 깔 CSS 그라데이션. */
  fallback: string;
  /** 1.0이면 원본 속도. 대기 화면이라 느리게 흐르는 편이 낫다. */
  speed?: number;
  /**
   * 렌더 배율. 아이패드에서 실측으로 정한다.
   * 뭉개져 보이면 2, 발열이 심하거나 조작이 버벅이면 1.
   */
  dpr?: number;
  /** 화면이 가려졌을 때 렌더를 멈춘다. */
  paused?: boolean;
};

export function KioskAura({ color, fallback, speed = 0.6, dpr = 1.5, paused = false }: Props) {
  const hostRef = useRef<HTMLDivElement>(null);

  /**
   * 목표 색. 이걸 ref로 두는 것이 이 컴포넌트의 핵심이다.
   * state로 두면 색이 바뀔 때마다 효과가 다시 돌아 컨텍스트가 새로 만들어진다.
   */
  const targetRef = useRef(color);
  const pausedRef = useRef(paused);

  useEffect(() => {
    targetRef.current = color;
  }, [color]);

  useEffect(() => {
    pausedRef.current = paused;
  }, [paused]);

  /** 컨텍스트가 복구되면 올려서 초기화를 다시 태운다. */
  const [generation, setGeneration] = useState(0);

  useEffect(() => {
    const host = hostRef.current;
    if (host === null) return;

    // WebGL 자체를 못 쓰는 환경이면 조용히 폴백으로 간다.
    // 캔버스를 안 붙이기만 하면 아래 깔아둔 CSS 그라데이션이 그대로 보인다.
    let renderer: Renderer;
    try {
      renderer = new Renderer({ dpr, alpha: false, antialias: false });
    } catch {
      return;
    }

    const gl = renderer.gl;
    gl.clearColor(CLEAR[0], CLEAR[1], CLEAR[2], 1);

    const canvas = gl.canvas as HTMLCanvasElement;
    canvas.style.width = "100%";
    canvas.style.height = "100%";
    canvas.style.display = "block";
    // 첫 프레임을 그리기 전까지는 투명하게 둔다. 불투명한 빈 캔버스가
    // 아래 깔린 CSS 그라데이션을 덮으면, 셰이더가 안 도는 상황에서
    // 화면이 통째로 검게 보인다(rAF가 멈추는 환경이 실제로 있다).
    canvas.style.opacity = "0";
    canvas.style.transition = "opacity 600ms ease";

    const program = new Program(gl, {
      vertex: vertexShader,
      fragment: fragmentShader,
      uniforms: {
        uTime: { value: 0 },
        // 시작 색은 목표 색 그대로. 첫 진입에서 색이 흘러가면 어수선하다.
        uColor: { value: new Color(...targetRef.current) },
        uResolution: { value: new Color(1, 1, 1) },
        uSpeed: { value: speed },
      },
    });

    const mesh = new Mesh(gl, { geometry: new Triangle(gl), program });

    function resize() {
      const w = host!.offsetWidth;
      const h = host!.offsetHeight;
      if (w === 0 || h === 0) return;
      renderer.setSize(w, h);
      program.uniforms.uResolution.value = new Color(
        gl.canvas.width,
        gl.canvas.height,
        gl.canvas.width / gl.canvas.height
      );
    }

    // KioskFrame이 transform으로 확대하므로 창 크기 이벤트만으로는 부족하다.
    const observer = new ResizeObserver(resize);
    observer.observe(host);
    resize();

    host.appendChild(canvas);

    // ── 렌더 루프 ────────────────────────────────────────────
    let raf = 0;
    let lastFrame = 0;
    /** 멈춰 있는 동안은 시간이 흐르지 않게 따로 적산한다. 안 그러면 복귀할 때 튄다. */
    let elapsed = 0;

    function update(now: number) {
      raf = requestAnimationFrame(update);

      // lastFrame을 dt 계산 뒤에 갱신하면 첫 프레임이 0으로 걸러지면서
      // lastFrame이 영영 0에 머문다. 한 프레임도 그려지지 않는다.
      if (lastFrame === 0) lastFrame = now;
      const dt = now - lastFrame;
      if (dt < FRAME_MS) return;
      lastFrame = now;

      if (pausedRef.current) return;

      const dtS = Math.min(dt, 250) / 1000; // 탭 복귀 직후의 큰 dt를 자른다
      elapsed += dtS;
      program.uniforms.uTime.value = elapsed;

      // 목표 색으로 지수 보간. 프레임 간격이 흔들려도 속도가 일정하다.
      const k = 1 - Math.exp(-dtS / COLOR_TAU_S);
      const cur = program.uniforms.uColor.value as Color;
      const [tr, tg, tb] = targetRef.current;
      cur.r += (tr - cur.r) * k;
      cur.g += (tg - cur.g) * k;
      cur.b += (tb - cur.b) * k;

      renderer.render({ scene: mesh });

      if (canvas.style.opacity !== "1") canvas.style.opacity = "1";
    }
    raf = requestAnimationFrame(update);

    // ── 컨텍스트 손실 ────────────────────────────────────────
    function onLost(e: Event) {
      e.preventDefault(); // 이걸 불러야 복구 이벤트가 온다
      cancelAnimationFrame(raf);
      // 죽은 캔버스를 투명하게 만들면 아래 깔린 CSS 그라데이션이 드러난다.
      canvas.style.opacity = "0";
    }
    function onRestored() {
      setGeneration((g) => g + 1);
    }
    canvas.addEventListener("webglcontextlost", onLost);
    canvas.addEventListener("webglcontextrestored", onRestored);

    return () => {
      cancelAnimationFrame(raf);
      observer.disconnect();
      canvas.removeEventListener("webglcontextlost", onLost);
      canvas.removeEventListener("webglcontextrestored", onRestored);
      canvas.remove();
      gl.getExtension("WEBGL_lose_context")?.loseContext();
    };
    // color는 일부러 뺐다. 색은 uniform으로만 갱신한다.
  }, [dpr, speed, generation]);

  return (
    <div
      ref={hostRef}
      aria-hidden
      className="absolute inset-0 overflow-hidden"
      style={{
        // 셰이더가 살아 있어도 아래 깔아둔다. 초기 한 프레임과 복구 사이를 메운다.
        background: fallback,
        transition: "background 1.2s ease",
      }}
    />
  );
}

export default KioskAura;
