-- Gatos de um evento com mais de um animal no quadro. Quando ha um gato so, a
-- identificacao continua em events.pet_id; esta tabela existe para o caso em
-- que nenhuma atribuicao unica faria sentido.
CREATE TABLE event_pets (
    event_id TEXT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    pet_id TEXT NOT NULL REFERENCES pets(id) ON DELETE CASCADE,
    PRIMARY KEY (event_id, pet_id)
);

CREATE INDEX idx_event_pets_pet ON event_pets(pet_id);
