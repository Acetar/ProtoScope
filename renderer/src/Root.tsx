import React from 'react';
import {Composition, type CalculateMetadataFunction} from 'remotion';
import {Handshake} from './compositions/Handshake';
import {handshakeDefaultProps} from './props/handshake';
import type {AnimationProps} from './schema/animation';

/**
 * props 里带着总帧数，渲染时按它算时长。
 * 没有这个，CLI 只会用 Composition 上写死的 durationInFrames，
 * 生成出来的 12s / 24s 动画就会被截断或补黑帧。
 */
const calculateMetadata: CalculateMetadataFunction<AnimationProps> = ({props}) => ({
  durationInFrames: props.totalFrames,
  fps: props.fps,
  width: props.width,
  height: props.height,
});

/** 通用模板：任何"两方消息往来"的协议都能套 */
const protocolFlowDefaultProps: AnimationProps = {
  ...handshakeDefaultProps,
  templateId: 'ProtocolFlow',
};

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="ProtocolFlow"
        component={Handshake}
        durationInFrames={protocolFlowDefaultProps.totalFrames}
        fps={protocolFlowDefaultProps.fps}
        width={protocolFlowDefaultProps.width}
        height={protocolFlowDefaultProps.height}
        defaultProps={protocolFlowDefaultProps}
        calculateMetadata={calculateMetadata}
      />
      <Composition
        id="Handshake"
        component={Handshake}
        durationInFrames={handshakeDefaultProps.totalFrames}
        fps={handshakeDefaultProps.fps}
        width={handshakeDefaultProps.width}
        height={handshakeDefaultProps.height}
        defaultProps={handshakeDefaultProps}
        calculateMetadata={calculateMetadata}
      />
    </>
  );
};
