import { useEffect, useId, useRef, useState } from 'react'
import * as api from '../api'
import type { AppSettings } from '../api'
import type { View } from '../lib/views'
import { viewLabels } from '../lib/views'
import { errorMessage } from '../lib/errors'
import Icon, { type IconName } from './Icon'

const feedbackEmail = 'lucascode@gmail.com'
const feedbackSubject = encodeURIComponent('Monitora Pet — erro ou sugestão')
const feedbackBody = encodeURIComponent(
  'Versão do app:\n\nO que eu estava fazendo:\n\nO que aconteceu ou minha sugestão:\n\nO que eu esperava:\n',
)

const steps: { title: string; text: string; tip: string; view: View; icon: IconName; action: string }[] = [
  {
    title: 'Vamos conhecer o Monitora Pet?',
    text: 'O Monitora Pet está em desenvolvimento. Algumas funcionalidades podem mudar e você pode encontrar erros. Seu feedback ajuda a melhorar o aplicativo.',
    tip: 'Ao relatar um erro ou enviar uma sugestão, conte o que estava fazendo, o que aconteceu e o que esperava. Se possível, inclua uma captura de tela e a versão do app, disponível em Configurações. Seu progresso neste guia fica salvo para continuar depois.',
    view: 'dashboard',
    icon: 'pets',
    action: 'Ver o painel',
  },
  {
    title: 'Cadastre seus pets',
    text: 'Abra Pets, adicione o nome e uma foto de cada animal da casa para ajudar na identificação dos registros.',
    tip: 'Use uma foto nítida, com apenas um pet, rosto e pelagem bem visíveis, boa iluminação e fundo simples. Evite fotos escuras, desfocadas ou com objetos cobrindo o animal. Se seus gatos ou cachorros forem muito parecidos, coleiras de cores diferentes podem ajudar a distingui-los nas imagens e nas revisões. Se usarem coleira no dia a dia, inclua esse detalhe na foto de cadastro. O reconhecimento automático ainda pode confundir animais semelhantes.',
    view: 'pets',
    icon: 'pets',
    action: 'Abrir Pets',
  },
  {
    title: 'Posicione e configure a câmera',
    text: 'Fixe a câmera em um ponto estável, em altura intermediária e com leve inclinação para baixo. Busque uma visão de frente ou de lado, mostrando o rosto, a lateral do corpo e as patas do pet, além do local da atividade e do espaço de aproximação.',
    tip: 'A câmera deve permanecer fixa, sem girar ou acompanhar o pet. Desative movimentos automáticos, patrulha e rastreamento, pois eles mudam o enquadramento e desalinhariam as zonas cadastradas. Se reposicionar a câmera, ajuste as zonas novamente. Evite uma visão muito de cima, mostrando só as costas do pet, ou uma câmera rente ao chão. O detector atual pode ter dificuldade com o ângulo superior. Use boa iluminação e deixe a visão livre de obstáculos. O modo noturno da câmera também funciona muito bem para acompanhar os pets à noite. Confira o enquadramento na prévia antes de criar as zonas. Em Câmeras, configure uma câmera da rede ou uma câmera manual para importar gravações.',
    view: 'cameras',
    icon: 'camera',
    action: 'Abrir Câmeras',
  },
  {
    title: 'Desenhe as áreas monitoradas',
    text: 'Em Áreas monitoradas, escolha a câmera e clique na imagem para marcar pelo menos três pontos ao redor do local da atividade. Informe um nome, selecione o tipo da área e salve.',
    tip: 'Inclua o espaço ocupado pelo pet durante a atividade, sem abranger o ambiente inteiro. Crie uma zona para cada local e evite sobreposições. Arraste os pontos para ajustar o contorno. Se mover a câmera, ajuste as zonas novamente.',
    view: 'zones',
    icon: 'zones',
    action: 'Abrir Áreas monitoradas',
  },
  {
    title: 'Acompanhe os registros',
    text: 'No Histórico, filtre por pet, área e período. Use a estrela para guardar os registros nos favoritos.',
    tip: 'Os registros aparecem depois que o sistema analisa as imagens ou gravações.',
    view: 'history',
    icon: 'history',
    action: 'Abrir Histórico',
  },
  {
    title: 'Ajude o app a reconhecer seu pet',
    text: 'Em Revisões, confira as imagens e confirme ou corrija qual pet aparece. Essas respostas ajudam o sistema a aprender localmente a reconhecer o seu gato ou cachorro e a ajustar a identificação para os animais da sua casa.',
    tip: 'Quanto mais identificações você revisar corretamente, mais exemplos o sistema terá para melhorar o reconhecimento. Com exemplos suficientes e a revisão automática ativada, os registros mais confiáveis podem ser aprovados automaticamente. Continue conferindo os casos em dúvida. Você pode rever este guia pelo botão Tutorial no topo.',
    view: 'reviews',
    icon: 'reviews',
    action: 'Abrir Revisões',
  },
]

type Props = {
  settings: AppSettings
  onSettings: (settings: AppSettings) => void
  onNavigate: (view: View) => void
  onClose: () => void
}

export default function Tutorial({ settings, onSettings, onNavigate, onClose }: Props) {
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [feedbackOpen, setFeedbackOpen] = useState(false)
  const [copyMessage, setCopyMessage] = useState('')
  const index = settings.tutorial.step
  const step = steps[index] ?? steps[0]
  const titleId = useId()
  const dialog = useRef<HTMLElement>(null)
  const [target, setTarget] = useState<{
    top: number
    left: number
    width: number
    height: number
    mobile: boolean
  } | null>(null)

  useEffect(() => {
    let frame = 0
    const measure = () => {
      cancelAnimationFrame(frame)
      frame = requestAnimationFrame(() => {
        const mobile = window.innerWidth <= 620
        const element = document.querySelector(mobile ? '.menu-toggle' : `[data-tutorial-view="${step.view}"]`)
        const bounds = element?.getBoundingClientRect()
        setTarget(
          bounds && bounds.width > 0
            ? {
                top: bounds.top,
                left: bounds.left,
                width: bounds.width,
                height: bounds.height,
                mobile,
              }
            : null,
        )
      })
    }
    measure()
    window.addEventListener('resize', measure)
    window.addEventListener('scroll', measure, true)
    return () => {
      cancelAnimationFrame(frame)
      window.removeEventListener('resize', measure)
      window.removeEventListener('scroll', measure, true)
    }
  }, [step.view])

  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null
    dialog.current?.focus()
    return () => {
      if (previous?.isConnected && !previous.closest('[inert]')) previous.focus()
    }
  }, [])

  async function save(next: number, status: AppSettings['tutorial']['status'] = 'active') {
    if (saving) return
    setSaving(true)
    setError('')
    try {
      onSettings(await api.updateTutorial(next, status))
    } catch (reason) {
      setError(errorMessage(reason, 'Não foi possível salvar o progresso. Tente novamente.'))
    } finally {
      setSaving(false)
    }
  }

  async function copyEmail() {
    try {
      await navigator.clipboard.writeText(feedbackEmail)
      setCopyMessage('E-mail copiado!')
    } catch {
      setCopyMessage(`Copie o endereço: ${feedbackEmail}`)
    }
  }

  return (
    <div className="modal-backdrop onboarding tutorial-backdrop">
      {index > 0 && target && (
        <div
          className={`tutorial-menu-marker${target.mobile ? ' mobile' : ''}`}
          style={{ top: target.top, left: target.left, width: target.width, height: target.height }}
          aria-hidden="true"
        >
          <Icon name={target.mobile ? 'menu' : step.icon} />
          {!target.mobile && <strong>{viewLabels[step.view]}</strong>}
        </div>
      )}
      <section
        ref={dialog}
        className="modal tutorial-card"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-busy={saving}
        tabIndex={-1}
        onKeyDown={event => {
          if (event.key === 'Escape' && !saving) onClose()
          if (event.key !== 'Tab') return
          const controls = Array.from(
            event.currentTarget.querySelectorAll<HTMLElement>('button:not(:disabled), a[href]'),
          )
          const first = controls[0]
          const last = controls[controls.length - 1]
          if (event.shiftKey && (document.activeElement === first || document.activeElement === dialog.current)) {
            event.preventDefault()
            last?.focus()
          } else if (
            !event.shiftKey &&
            (document.activeElement === last || document.activeElement === dialog.current)
          ) {
            event.preventDefault()
            first?.focus()
          }
        }}
      >
        <button
          type="button"
          className="tutorial-close"
          aria-label="Fechar e continuar depois"
          disabled={saving}
          onClick={onClose}
        >
          <Icon name="close" />
        </button>
        <div className="tutorial-body">
          <div className="tutorial-header">
            <div className="tutorial-icon">
              <Icon name={step.icon} />
            </div>
            <p className="eyebrow">
              PRIMEIROS PASSOS · {index + 1} DE {steps.length}
            </p>
          </div>
          <div aria-live="polite">
            <h2 id={titleId}>{step.title}</h2>
            <p>{step.text}</p>
            <p className="tutorial-tip">{step.tip}</p>
            {index === 1 && (
              <div className="tutorial-examples tutorial-profile-examples">
                <figure className="tutorial-example ideal">
                  <img
                    src="/tutorial/pet-profile-ideal.png"
                    alt="Gato sozinho, com rosto e pelagem nítidos, boa iluminação e fundo simples."
                    width="1254"
                    height="1254"
                  />
                  <figcaption>
                    <strong>
                      <Icon name="accept" /> Boa foto de perfil
                    </strong>
                    <span>Um pet por foto, bem enquadrado e sem obstáculos.</span>
                  </figcaption>
                </figure>
                <figure className="tutorial-example poor">
                  <img
                    src="/tutorial/pet-profile-poor.png"
                    alt="Foto escura e desfocada, com o gato de costas e objetos cobrindo parte do corpo."
                    width="1254"
                    height="1254"
                  />
                  <figcaption>
                    <strong>
                      <Icon name="close" /> Foto inadequada
                    </strong>
                    <span>Pouca luz, rosto escondido e pelagem sem nitidez.</span>
                  </figcaption>
                </figure>
              </div>
            )}
            {index > 0 && (
              <p className="tutorial-location">
                {target?.mobile ? 'Abra o menu no topo e selecione' : 'No menu à esquerda, selecione'}{' '}
                <strong>{viewLabels[step.view]}</strong>.
              </p>
            )}
            {(index === 2 || index === 3) && (
              <div className="tutorial-examples">
                <figure className="tutorial-example ideal">
                  <img
                    src={index === 2 ? '/tutorial/camera-ideal-v2.png' : '/tutorial/zone-ideal.png'}
                    alt={
                      index === 2
                        ? 'Visão lateral com leve inclinação para baixo, mostrando o rosto, o corpo inteiro do gato e os potes, sem obstáculos.'
                        : 'Zona verde concentrada no bebedouro e no espaço ocupado pelo gato durante a atividade.'
                    }
                    width="1536"
                    height="1024"
                  />
                  <figcaption>
                    <strong>
                      <Icon name="accept" /> {index === 2 ? 'Posicionamento ideal' : 'Zona bem definida'}
                    </strong>
                    <span>
                      {index === 2
                        ? 'Altura intermediária, rosto e lateral do corpo visíveis.'
                        : 'Contorno focado na atividade, com espaço para o pet.'}
                    </span>
                  </figcaption>
                </figure>
                <figure className="tutorial-example poor">
                  <img
                    src={`/tutorial/${index === 2 ? 'camera' : 'zone'}-poor.png`}
                    alt={
                      index === 2
                        ? 'Câmera muito baixa, com cadeira obstruindo o gato e luz forte atrás do animal.'
                        : 'Zona vermelha ampla demais, cobrindo o chão e espaços sem relação com a atividade.'
                    }
                    width="1536"
                    height="1024"
                  />
                  <figcaption>
                    <strong>
                      <Icon name="close" /> {index === 2 ? 'Posicionamento inadequado' : 'Zona ampla demais'}
                    </strong>
                    <span>
                      {index === 2
                        ? 'Obstáculos, pet cortado e luz contra a câmera.'
                        : 'Espaços sem relação podem gerar registros indevidos.'}
                    </span>
                  </figcaption>
                </figure>
              </div>
            )}
            {index === 0 && (
              <div>
                <button
                  type="button"
                  className="tutorial-feedback"
                  aria-expanded={feedbackOpen}
                  aria-controls={`${titleId}-feedback`}
                  onClick={() => setFeedbackOpen(value => !value)}
                >
                  Enviar erro ou sugestão por e-mail
                </button>
                {feedbackOpen && (
                  <div className="tutorial-feedback-options" id={`${titleId}-feedback`}>
                    <p>
                      Envie sua mensagem para <strong>{feedbackEmail}</strong>.
                    </p>
                    <div className="tutorial-actions">
                      <a
                        className="secondary"
                        href={`https://mail.google.com/mail/?view=cm&fs=1&to=${feedbackEmail}&su=${feedbackSubject}&body=${feedbackBody}`}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        Escrever no Gmail
                      </a>
                      <a
                        className="secondary"
                        href={`mailto:${feedbackEmail}?subject=${feedbackSubject}&body=${feedbackBody}`}
                      >
                        Abrir aplicativo de e-mail
                      </a>
                      <button type="button" className="secondary" onClick={() => void copyEmail()}>
                        Copiar e-mail
                      </button>
                    </div>
                    <p className="tutorial-tip">
                      A opção de aplicativo precisa de um e-mail configurado no computador. Pelo Gmail, você escreve no
                      navegador.
                    </p>
                    <p role="status">{copyMessage}</p>
                  </div>
                )}
              </div>
            )}
          </div>
          <div className="tutorial-progress" aria-hidden="true">
            {steps.map((_, position) => (
              <span key={position} className={position <= index ? 'done' : ''} />
            ))}
          </div>
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
          <div className="tutorial-actions">
            <button className="secondary" disabled={saving} onClick={() => onNavigate(step.view)}>
              {step.action}
            </button>
            <button className="tutorial-skip" disabled={saving} onClick={() => void save(index, 'skipped')}>
              Pular tutorial
            </button>
            <div className="tutorial-navigation">
              {index > 0 && (
                <button className="secondary" disabled={saving} onClick={() => void save(index - 1)}>
                  Voltar
                </button>
              )}
              <button
                className="primary"
                disabled={saving}
                onClick={() => void save(Math.min(index + 1, 5), index === 5 ? 'completed' : 'active')}
              >
                {saving ? 'Salvando…' : index === 5 ? 'Concluir tutorial' : 'Próximo'}
              </button>
            </div>
          </div>
        </div>
      </section>
    </div>
  )
}
