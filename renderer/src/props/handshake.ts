import type {AnimationProps} from '../schema/animation';

/**
 * 默认 props：TCP 三次握手（18s / 30fps / 1920x1080）。
 * 生产环境中，这份 JSON 由大模型 + 规则后处理生成，经 Zod 校验后写入 animations.input_props。
 */
export const handshakeDefaultProps: AnimationProps = {
  knowledgePoint: 'tcp.handshake',
  templateId: 'Handshake',
  title: 'TCP 三次握手',
  subtitle: '为什么建立连接需要三个来回？',
  fps: 30,
  width: 1920,
  height: 1080,
  totalFrames: 540,
  actors: [
    {
      id: 'client',
      label: '客户端',
      icon: 'laptop',
      x: 300,
      y: 250,
      initialState: 'CLOSED',
    },
    {
      id: 'server',
      label: '服务端',
      icon: 'server',
      x: 1000,
      y: 250,
      initialState: 'LISTEN',
    },
  ],
  scenes: [
    {
      id: 'scene-1',
      title: '第一次握手 · SYN',
      startFrame: 0,
      durationInFrames: 180,
      narration: '客户端请求建立连接，携带初始序号 ISN(c)=100。此时它还不知道服务端是否在线。',
      actions: [
        {type: 'pulse', actor: 'client', delay: 6},
        {
          type: 'packet-fly',
          from: 'client',
          to: 'server',
          label: 'SYN',
          delay: 20,
          durationInFrames: 60,
          fields: {seq: '100', flags: 'SYN'},
          color: '#ffb454',
        },
        {type: 'state-change', actor: 'client', from: 'CLOSED', to: 'SYN_SENT', delay: 20},
      ],
    },
    {
      id: 'scene-2',
      title: '第二次握手 · SYN + ACK',
      startFrame: 180,
      durationInFrames: 180,
      narration: '服务端确认收到 100，同时发出自己的初始序号 ISN(s)=300。一次报文承担两个语义。',
      actions: [
        {
          type: 'packet-fly',
          from: 'server',
          to: 'client',
          label: 'SYN + ACK',
          delay: 20,
          durationInFrames: 60,
          fields: {seq: '300', ack: '101', flags: 'SYN, ACK'},
          color: '#38e1ff',
        },
        {type: 'state-change', actor: 'server', from: 'LISTEN', to: 'SYN_RCVD', delay: 20},
      ],
    },
    {
      id: 'scene-3',
      title: '第三次握手 · ACK',
      startFrame: 360,
      durationInFrames: 180,
      narration: '客户端确认服务端的序号 300，双方进入 ESTABLISHED，可以开始传数据。',
      actions: [
        {
          type: 'packet-fly',
          from: 'client',
          to: 'server',
          label: 'ACK',
          delay: 20,
          durationInFrames: 60,
          fields: {seq: '101', ack: '301', flags: 'ACK'},
          color: '#3ddc97',
        },
        {type: 'state-change', actor: 'client', from: 'SYN_SENT', to: 'ESTABLISHED', delay: 84},
        {type: 'state-change', actor: 'server', from: 'SYN_RCVD', to: 'ESTABLISHED', delay: 84},
      ],
    },
  ],
  captions: [
    {startFrame: 24, endFrame: 150, text: '① 客户端发送 SYN，声明自己的初始序号 seq=100'},
    {startFrame: 204, endFrame: 330, text: '② 服务端回 SYN+ACK：确认 101，同时声明 seq=300'},
    {startFrame: 384, endFrame: 512, text: '③ 客户端回 ACK：确认 301，连接建立'},
  ],
  audioSrc: null,
};
