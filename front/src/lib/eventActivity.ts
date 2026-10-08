import type { Event } from '../api'

export function activityEvents(events: Event[], petId = ''): Event[] {
  return events.filter(
    event =>
      event.review_decision !== 'NO_ACTION' &&
      event.review_decision !== 'FALSE_POSITIVE' &&
      (!petId || event.pet_id === petId),
  )
}
