import { renderHook, act } from '@testing-library/react';
import { JSDOM } from 'jsdom';
import { Fragment, ReactNode, createElement, useEffect } from 'react';
import { RecoilRoot, useRecoilValue } from 'recoil';
import { describe, expect, it, vi } from 'vitest';

import { ChainlitContext } from './context';
import {
  useChatSession,
  SOCKET_IO_RECONNECTION_OPTIONS,
  RECONNECTION_ATTEMPTS,
  RECONNECTION_DELAY_MS,
  RECONNECTION_DELAY_MAX_MS,
  SOCKET_IO_RECONNECTION_BASE_DELAY_MS,
  SOCKET_IO_RECONNECTION_BACKOFF_FACTOR
} from './useChatSession';
import { mcpState, wavRecorderState, wavStreamPlayerState } from 'src/state';
import type { IMcp } from 'src/types';

vi.mock('./api', () => ({
  ChainlitAPI: class ChainlitAPI {}
}));
const jsdom = new JSDOM('<!doctype html><html><body></body></html>');
(globalThis as any).window = jsdom.window;
(globalThis as any).document = jsdom.window.document;
Object.defineProperty(globalThis, 'navigator', {
  value: jsdom.window.navigator,
  configurable: true
});
(jsdom.window as any).$recoilDebugStates = [];
const mockIo = vi.fn();
vi.mock('socket.io-client', () => ({
  __esModule: true,
  default: (...args: any[]) => mockIo(...args)
}));

const toastMock = Object.assign(vi.fn(), {
  info: vi.fn(),
  error: vi.fn(),
  success: vi.fn(),
  warning: vi.fn()
});

vi.mock('sonner', () => ({
  toast: toastMock
}));

const McpStateObserver = ({ onChange }: { onChange: (value: IMcp[]) => void }) => {
  const value = useRecoilValue(mcpState);
  useEffect(() => {
    onChange(value);
  }, [onChange, value]);

  return null;
};

describe('useChatSession', () => {
  it('retries websocket connection with exponential backoff configuration', async () => {
    const socket = {
      on: vi.fn(),
      emit: vi.fn(),
      close: vi.fn(),
      removeAllListeners: vi.fn()
    };

    mockIo.mockReturnValue(socket);

    const clientStub = {
      httpEndpoint: 'https://example.com/api',
      type: 'webapp',
      stickyCookie: vi.fn().mockResolvedValue(undefined)
    } as any;

    const wrapper = ({ children }: { children: ReactNode }) =>
      createElement(
        ChainlitContext.Provider,
        { value: clientStub },
        createElement(
          RecoilRoot,
          {
            initializeState: ({ set }) => {
              set(
                wavRecorderState,
                {
                  begin: vi.fn(),
                  record: vi.fn(),
                  end: vi.fn()
                } as any
              );
              set(
                wavStreamPlayerState,
                {
                  connect: vi.fn(),
                  add16BitPCM: vi.fn(),
                  interrupt: vi.fn()
                } as any
              );
            },
            children
          }
        )
      );

    const { result } = renderHook(() => useChatSession(), { wrapper });

    await act(async () => {
      result.current.connect({ userEnv: {} });
      await (result.current.connect as any).flush?.();
    });

    expect(mockIo).toHaveBeenCalledTimes(1);
    const [, options] = mockIo.mock.calls[0];
    expect(options).toMatchObject(SOCKET_IO_RECONNECTION_OPTIONS);
    expect(options.reconnectionAttempts).toBe(RECONNECTION_ATTEMPTS);
    expect(options.reconnectionDelay).toBe(RECONNECTION_DELAY_MS);
    expect(options.reconnectionDelayMax).toBe(RECONNECTION_DELAY_MAX_MS);
    expect(options).toMatchObject({
      ...SOCKET_IO_RECONNECTION_OPTIONS,
      reconnectionDelay: SOCKET_IO_RECONNECTION_BASE_DELAY_MS,
      reconnectionDelayMax:
        SOCKET_IO_RECONNECTION_BASE_DELAY_MS *
        SOCKET_IO_RECONNECTION_BACKOFF_FACTOR ** 2
    });
  });

  it('fails SSE connection after three attempts while preserving exponential backoff delays', async () => {
    vi.useFakeTimers();
    const socketHandlers: Record<string, (...args: any[]) => void> = {};
    const socket = {
      on: vi.fn((event: string, handler: (...args: any[]) => void) => {
        socketHandlers[event] = handler;
        return socket;
      }),
      emit: vi.fn(),
      close: vi.fn(),
      removeAllListeners: vi.fn()
    };

    mockIo.mockReturnValue(socket);

    const connectSseMCP = vi.fn().mockRejectedValue(new Error('network-error'));

    const observedStates: IMcp[][] = [];

    const clientStub = {
      httpEndpoint: 'https://example.com/api',
      type: 'webapp',
      stickyCookie: vi.fn().mockResolvedValue(undefined),
      connectSseMCP
    } as any;

    const setTimeoutSpy = vi.spyOn(globalThis, 'setTimeout');

    const wrapper = ({ children }: { children: ReactNode }) =>
      createElement(
        ChainlitContext.Provider,
        { value: clientStub },
        createElement(
          RecoilRoot,
          {
            initializeState: ({ set }) => {
              set(
                mcpState,
                [
                  {
                    name: 'sse-mcp',
                    status: 'connecting',
                    clientType: 'sse',
                    url: 'https://example.com/mcp',
                    tools: [{ name: 'tool' }]
                  }
                ] as IMcp[]
              );
              set(
                wavRecorderState,
                {
                  begin: vi.fn(),
                  record: vi.fn(),
                  end: vi.fn()
                } as any
              );
              set(
                wavStreamPlayerState,
                {
                  connect: vi.fn(),
                  add16BitPCM: vi.fn(),
                  interrupt: vi.fn()
                } as any
              );
            },
            children: createElement(
              Fragment,
              null,
              createElement(McpStateObserver, {
                onChange: (value) => {
                  observedStates.push(value);
                }
              }),
              children
            )
          }
        )
      );

    const { result } = renderHook(() => useChatSession(), { wrapper });

    await act(async () => {
      result.current.connect({ userEnv: {} });
      await (result.current.connect as any).flush?.();
    });

    expect(mockIo).toHaveBeenCalledTimes(1);

    await act(async () => {
      socketHandlers['connect']?.();
      await Promise.resolve();
    });

    expect(connectSseMCP).toHaveBeenCalledTimes(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(RECONNECTION_DELAY_MS);
      await Promise.resolve();
    });

    expect(connectSseMCP).toHaveBeenCalledTimes(2);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(RECONNECTION_DELAY_MS * 2);
      await Promise.resolve();
    });

    expect(connectSseMCP).toHaveBeenCalledTimes(3);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(RECONNECTION_DELAY_MAX_MS);
      await Promise.resolve();
    });

    expect(connectSseMCP).toHaveBeenCalledTimes(3);

    expect(
      observedStates.slice(0, -1).every((state) => state[0].status === 'connecting')
    ).toBe(true);
    expect(observedStates.at(-1)?.[0].status).toBe('failed');
    expect(toastMock.error).toHaveBeenCalledWith(
      'Failed to connect to sse-mcp after 3 attempts.'
    );

    const delays = setTimeoutSpy.mock.calls
      .map(([, timeout]) => timeout)
      .filter((value): value is number => typeof value === 'number');
    expect(delays.length).toBeGreaterThanOrEqual(3);
    expect(delays.slice(0, 3)).toEqual([
      RECONNECTION_DELAY_MS,
      RECONNECTION_DELAY_MS * 2,
      RECONNECTION_DELAY_MAX_MS
    ]);

    setTimeoutSpy.mockRestore();
    vi.useRealTimers();
  });
});
