import { render } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';

import AppWrapper from '../src/AppWrapper';

const windowMessageMock = vi.fn();

vi.mock('@chainlit/react-client', () => ({
  useChatInteract: () => ({ windowMessage: windowMessageMock }),
  useAuth: () => ({ isAuthenticated: true, isReady: true }),
  useConfig: () => ({ language: 'en' }),
  useApi: () => ({ data: { translation: {} } })
}));

const changeLanguageMock = vi.fn();
const addResourceBundleMock = vi.fn();

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    i18n: {
      changeLanguage: changeLanguageMock,
      addResourceBundle: addResourceBundleMock
    }
  })
}));

vi.mock('../src/lib/router', () => ({
  default: () => ''
}));

vi.mock('App', () => ({
  default: () => <div data-testid="app-root">App</div>
}));

describe('AppWrapper', () => {
  beforeEach(() => {
    windowMessageMock.mockClear();
  });

  it('ignores cross-origin window messages', () => {
    render(<AppWrapper />);

    window.dispatchEvent(
      new MessageEvent('message', { data: 'cross', origin: 'https://evil.example' })
    );

    expect(windowMessageMock).not.toHaveBeenCalled();

    window.dispatchEvent(
      new MessageEvent('message', {
        data: 'trusted',
        origin: window.location.origin
      })
    );

    expect(windowMessageMock).toHaveBeenCalledWith('trusted');
  });
});
