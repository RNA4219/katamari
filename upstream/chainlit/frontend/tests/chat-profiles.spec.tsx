import { render, waitFor } from '@testing-library/react';
import { type ReactNode, useEffect, useState } from 'react';
import { describe, expect, it, vi } from 'vitest';

import ChatProfiles from 'components/header/ChatProfiles';

vi.mock('@chainlit/react-client', () => {
  const React = require('react');

  interface ChatProfile {
    name: string;
    markdown_description?: string;
    icon?: string | null;
  }

  interface Config {
    chatProfiles: ChatProfile[];
    features?: { unsafe_allow_html?: boolean; latex?: boolean };
  }

  const ChainlitContext = React.createContext({
    buildEndpoint: (path: string) => path
  });

  const ConfigContext = React.createContext<{ config: Config | null }>({
    config: null
  });

  const ChatSessionContext = React.createContext({
    chatProfile: null as string | null,
    setChatProfile: () => {}
  });

  const ChatMessagesContext = React.createContext({
    firstInteraction: false
  });

  const ChatInteractContext = React.createContext({
    clear: () => {}
  });

  return {
    ChainlitContext,
    ConfigProvider: ConfigContext.Provider,
    ChatSessionProvider: ChatSessionContext.Provider,
    ChatMessagesProvider: ChatMessagesContext.Provider,
    ChatInteractProvider: ChatInteractContext.Provider,
    useConfig: () => React.useContext(ConfigContext),
    useChatSession: () => React.useContext(ChatSessionContext),
    useChatMessages: () => React.useContext(ChatMessagesContext),
    useChatInteract: () => React.useContext(ChatInteractContext)
  };
});

import {
  ChainlitContext,
  ConfigProvider,
  ChatInteractProvider,
  ChatMessagesProvider,
  ChatSessionProvider
} from '@chainlit/react-client';

const mockSetChatProfile = vi.fn();
const mockClear = vi.fn();

function Wrapper({ children }: { children: ReactNode }) {
  const [config, setConfig] = useState({
    chatProfiles: [] as Array<{
      name: string;
      markdown_description?: string;
      icon?: string | null;
    }>,
    features: {}
  });
  const [chatProfile, setChatProfile] = useState<string | null>(null);

  useEffect(() => {
    setConfig({
      chatProfiles: [
        {
          name: 'Profile A',
          markdown_description: 'First profile'
        },
        {
          name: 'Profile B',
          markdown_description: 'Second profile'
        }
      ],
      features: {}
    });
  }, []);

  return (
    <ChainlitContext.Provider value={{ buildEndpoint: (path: string) => path }}>
      <ConfigProvider value={{ config }}>
        <ChatSessionProvider
          value={{
            chatProfile,
            setChatProfile: (value: string) => {
              mockSetChatProfile(value);
              setChatProfile(value);
            }
          }}
        >
          <ChatMessagesProvider value={{ firstInteraction: false }}>
            <ChatInteractProvider value={{ clear: mockClear }}>
              {children}
            </ChatInteractProvider>
          </ChatMessagesProvider>
        </ChatSessionProvider>
      </ConfigProvider>
    </ChainlitContext.Provider>
  );
}

describe('ChatProfiles', () => {
  it('keeps hooks order stable when config updates from empty to populated', async () => {
    mockSetChatProfile.mockReset();

    render(
      <Wrapper>
        <ChatProfiles />
      </Wrapper>
    );

    await waitFor(() => {
      expect(mockSetChatProfile).toHaveBeenCalledWith('Profile A');
    });
  });
});
