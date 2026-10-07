import { useContext } from 'react'
import { HouseholdContext, HouseholdView } from './household'

export function useHousehold(): HouseholdView {
  return useContext(HouseholdContext)
}
