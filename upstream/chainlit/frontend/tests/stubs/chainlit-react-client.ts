import { createContext } from 'react';

export const ChainlitContext = createContext({
  buildEndpoint: (path: string) => path
});

export const useConfig = () => ({});

export interface IMessageElement {
  id: string;
  type: string;
  name?: string;
  display?: string;
  forId?: string;
  url?: string;
}

export interface IDataframeElement {
  id: string;
  type: 'dataframe';
  url?: string | null;
  name?: string;
  display?: string;
  forId?: string;
}

export interface IStep {
  id: string;
  threadId: string;
  type: string;
  name: string;
  createdAt: number;
  output?: string;
  input?: string;
  showInput?: boolean | string;
  streaming?: boolean;
  language?: string;
}
