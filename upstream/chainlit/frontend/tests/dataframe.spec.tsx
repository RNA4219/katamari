import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import DataframeElement from 'components/Elements/Dataframe';

import type { IDataframeElement } from '@chainlit/react-client';

vi.mock('hooks/useFetch', () => ({
  useFetch: () => ({
    data: JSON.stringify({
      index: [0],
      columns: ['First', 'Second'],
      data: [[123, 'value']]
    }),
    isLoading: false,
    error: null
  })
}));

describe('DataframeElement', () => {
  it('renders fetched dataframe content', () => {
    const element = {
      id: 'el-1',
      type: 'dataframe',
      url: '/fake',
      display: 'side',
      forId: 'msg-1',
      name: 'Sample Dataframe'
    } as IDataframeElement;

    render(<DataframeElement element={element} />);

    expect(screen.getByText('First')).toBeInTheDocument();
    expect(screen.getByText('Second')).toBeInTheDocument();
    expect(screen.getByText('123')).toBeInTheDocument();
    expect(screen.getByText('value')).toBeInTheDocument();
  });
});
