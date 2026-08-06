/**
 * devices.ts — the sensors a scan pretends to find.
 *
 * The first three are the ones drawn in the KARIRLINK Figma frame, so the mock
 * and the design show the same list. The fourth is deliberately not one the app
 * recognises: it exercises the path where the person has to be asked where they
 * wear it, which is the path most likely to be forgotten when every fixture is
 * a familiar brand.
 */

import { recogniseWearLocation, type HeartDevice } from '../types/device'

const NAMES = ['Polar H10', 'Coospo H808S', 'Magene H64', 'HRM-2938']

export const mockDiscoveredDevices: HeartDevice[] = NAMES.map((name, index) => ({
  id: `mock-${index}`,
  name,
  wornAt: recogniseWearLocation(name),
}))

/** How long a pretend scan takes, in milliseconds. */
export const MOCK_SCAN_MS = 900
