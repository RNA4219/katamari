import { renderHook, act } from '@testing-library/react';
import { JSDOM } from 'jsdom';
import { ReactNode, createElement } from 'react';
import { RecoilRoot } from 'recoil';
import { beforeEach, describe, expect, it, vi } from 'vitest';

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
import { wavRecorderState, wavStreamPlayerState } from 'src/state';

vi.mock('./api', () => ({
  ChainlitAPI: class ChainlitAPI {}
}));
const jsdom = new JSDOM('<!doctype html><html><body></body></html>', {
  url: 'https://app.example/app'
});
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

describe('useChatSession', () => {
  beforeEach(() => {
    mockIo.mockReset();
  });

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
          },
          children
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

  it('targets the application origin when emitting window messages', async () => {
    const socketHandlers: Record<string, (data: unknown) => void> = {};
    const socket = {
      on: vi.fn((event: string, handler: (data: unknown) => void) => {
        socketHandlers[event] = handler;
        return socket;
      }),
      emit: vi.fn(),
      close: vi.fn(),
      removeAllListeners: vi.fn()
    } as any;

    const postMessage = vi.fn();
    Object.defineProperty(window, 'parent', {
      value: { postMessage },
      configurable: true
    });

    Object.defineProperty(document, 'referrer', {
      value: 'https://malicious.example/embed',
      configurable: true
    });

    mockIo.mockReturnValue(socket);

    const clientStub = {
      httpEndpoint: 'https://app.example/api',
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
            }
          },
          children
        )
      );

    const { result } = renderHook(() => useChatSession(), { wrapper });

    await act(async () => {
      result.current.connect({ userEnv: {} });
      await (result.current.connect as any).flush?.();
    });

    expect(socketHandlers['window_message']).toBeDefined();

    await act(async () => {
      socketHandlers['window_message']?.({ foo: 'bar' });
    });

    expect(postMessage).toHaveBeenCalledWith({ foo: 'bar' }, 'https://app.example');
  });
});
