import { renderHook, act } from '@testing-library/react';
import { JSDOM } from 'jsdom';
import { ReactNode, createElement } from 'react';
import { RecoilRoot } from 'recoil';
import { describe, expect, it, vi } from 'vitest';

import { ChainlitContext } from './context';
import { useChatSession } from './useChatSession';
import { wavRecorderState, wavStreamPlayerState } from 'src/state';

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

    expect(mockIo).toHaveBeenCalledTimes(1);
    const [, options] = mockIo.mock.calls[0];
    expect(options).toMatchObject({
      reconnectionAttempts: 3,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 4000,
      randomizationFactor: 0
    });
  });
});
