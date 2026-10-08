-- A review that says there was no use is presence only, even when older
-- versions stored an eating/drinking/litter activity on the event.
UPDATE events
SET activity = 'NEAR_ZONE'
WHERE activity <> 'NEAR_ZONE'
  AND (SELECT r.decision FROM human_reviews r
       WHERE r.event_id = events.id
       ORDER BY r.created_at DESC LIMIT 1) = 'NO_ACTION';
