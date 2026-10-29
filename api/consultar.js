// Vercel Serverless Function - Proxy Oficial DataJud CNJ
export default async function handler(req, res) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type, Authorization");

  if (req.method === "OPTIONS") {
    return res.status(200).end();
  }

  if (req.method !== "POST") {
    return res.status(200).json({ status: "online", service: "iazjud-datajud-proxy" });
  }

  try {
    const body = req.body || {};
    const processo = body.processo;
    const tribunalHint = body.tribunal;

    if (!processo) {
      return res.status(400).json({ success: false, mensagem: "Número do processo é obrigatório" });
    }

    const numLimpo = String(processo).replace(/\D/g, "");
    
    // Mapeamento automático de tribunal pelo CNJ
    let trib = (tribunalHint || "").toLowerCase().trim();
    if (!trib && numLimpo.length >= 20) {
      const j = numLimpo.substring(13, 14);
      const tr = numLimpo.substring(14, 16);
      if (j === "8") {
        const tjs = { "06": "tjce", "26": "tjsp", "13": "tjmg", "19": "tjrj", "21": "tjrs", "16": "tjpr", "17": "tjpe", "05": "tjba" };
        trib = tjs[tr] || `tj${tr}`;
      } else if (j === "5") {
        trib = `trt${parseInt(tr, 10)}`;
      } else if (j === "4") {
        trib = `trf${parseInt(tr, 10)}`;
      } else if (j === "3") {
        trib = "stj";
      } else if (j === "1") {
        trib = "stf";
      }
    }
    if (!trib) trib = "tjce";

    const datajudUrl = `https://api-publica.datajud.cnj.jus.br/api_publica_${trib}/_search`;
    const datajudResp = await fetch(datajudUrl, {
      method: "POST",
      headers: {
        "Authorization": "APIKey cDZHYUpZa0JadVREZDJCendQbXY6SkJlTkxScEtTTEdBTUpDaWZ1MWh1TFlyZw==",
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        query: { match: { numeroProcesso: numLimpo } }
      })
    });

    if (!datajudResp.ok) {
      return res.status(datajudResp.status).json({
        success: false,
        mensagem: `Erro DataJud [${datajudResp.status}]`
      });
    }

    const json = await datajudResp.json();
    const hits = json.hits?.hits || [];
    if (!hits.length) {
      return res.json({ success: false, mensagem: "Processo não encontrado no DataJud para o tribunal informado." });
    }

    const fonte = hits[0]._source;
    const movs = (fonte.movimentos || []).map(m => ({
      dataHora: m.dataHora,
      nome: m.nome || m.descricao || "Movimentação registrada"
    }));

    return res.json({
      success: true,
      data: {
        processo: fonte.numeroProcesso,
        tribunal: trib.toUpperCase(),
        classe: fonte.classe?.nome,
        grau: fonte.grau,
        ultimaData: movs.length ? movs[0].dataHora : null,
        movimentos: movs
      }
    });
  } catch (err) {
    return res.status(500).json({ success: false, mensagem: err.message });
  }
}
