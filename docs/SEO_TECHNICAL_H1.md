# Mirai Hit Studio - SEO Technical H.1

## Canonicalização e indexação

- Host canônico: `https://miraihitstudio.com.br`.
- URLs indexáveis: `/`, `/artists`, `/creators`, `/media-games` e `/portfolio`.
- Cada URL indexável responde em 200, usa `rel=canonical` absoluto para si mesma e aparece no sitemap.
- Clean URLs não usam `.html` nem barra final. HTTP já redireciona para HTTPS.
- `www.miraihitstudio.com.br` ainda responde diretamente. Criar no dashboard Cloudflare uma Redirect Rule única, `www` para apex, com 308 e preservação de path/query. `_redirects` não é usado para redirect de domínio.

## Exclusões

- `/checkout` e `/checkout/<referencia>` não entram no sitemap. A Pages Function adiciona `X-Robots-Tag: noindex, nofollow, noarchive`; o documento também possui meta robots.
- `/admin` não entra no sitemap e possui meta robots e header `X-Robots-Tag` equivalentes. Isso não substitui autenticação.
- APIs, URLs de sessão, erros e referências de checkout não são listados nem possuem canonical público.

## Sitemap e robots

`robots.txt` permite rastreamento público e referencia o sitemap do host apex. O sitemap omite `lastmod`, `changefreq` e `priority`: não há fonte confiável para manter essas informações verdadeiras.

## Dados estruturados e compartilhamento

A Home usa apenas `Organization` JSON-LD com nome, URL, logo, descrição, Instagram público, e-mail público e área atendida já exibidos/assumidos pelo site. Não foram adicionados Service, MusicRecording, avaliações, preços, endereço ou BreadcrumbList: não há dados ou navegação visível suficientes para sustentá-los.

Open Graph e Twitter/X usam URLs canônicas absolutas e imagens existentes. O manifest agora referencia o favicon real.

## Search Console

1. Criar uma Domain property para `miraihitstudio.com.br` e concluir a verificação DNS.
2. Configurar o redirect `www` para apex no Cloudflare e validar que há só um salto.
3. Enviar `https://miraihitstudio.com.br/sitemap.xml`.
4. Inspecionar `/`, `/artists`, `/creators`, `/media-games` e `/portfolio`; solicitar indexação após validação.
5. Confirmar que checkout e admin aparecem como excluídos por `noindex` quando forem rastreados.
6. Executar o Rich Results Test na Home para validar Organization JSON-LD. Rich results não são garantidos mesmo com markup válido.

## Próximas fases

H.2 trata conteúdo, intenção de busca e páginas adicionais. H.3 trata performance e Core Web Vitals.
