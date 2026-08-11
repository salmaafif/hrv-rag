/**
 * stageContext.ts — what every stage screen receives from the layout.
 *
 * The device connection lives in `AppLayout` rather than in the start screen,
 * because it has to outlive that screen: you connect a sensor on stage one and
 * it must still be connected on stage two. Passing it down through the outlet
 * keeps that single instance without introducing a global store for two values.
 */

import type { ModeDefinition } from './modes'
import type { DeviceConnection } from './useDeviceConnection'
import type { SessionState } from './useSessionState'

export interface StageContext {
  mode: ModeDefinition
  device: DeviceConnection
  session: SessionState
}
