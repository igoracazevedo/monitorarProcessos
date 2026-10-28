-- ==============================================================================
-- MIGRAÇÃO DE TABELAS DO IAZ JUD: PREFIXO "ju_"
-- Projeto Supabase: kslmyvlewsmjnrhwklfd
-- ==============================================================================
-- Execute este script no SQL Editor do Supabase (https://supabase.com/dashboard/project/kslmyvlewsmjnrhwklfd/sql/new)

-- 1. Renomear tabelas principais do IAZ Jud (se existirem com o nome legado)
DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'processos') AND
       NOT EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'ju_processos') THEN
        ALTER TABLE public.processos RENAME TO ju_processos;
        RAISE NOTICE 'Tabela processos renomeada para ju_processos';
    END IF;

    IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'movimentacoes') AND
       NOT EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'ju_movimentacoes') THEN
        ALTER TABLE public.movimentacoes RENAME TO ju_movimentacoes;
        RAISE NOTICE 'Tabela movimentacoes renomeada para ju_movimentacoes';
    END IF;

    IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'empresas') AND
       NOT EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'ju_empresas') THEN
        ALTER TABLE public.empresas RENAME TO ju_empresas;
        RAISE NOTICE 'Tabela empresas renomeada para ju_empresas';
    END IF;

    IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'configuracoes') AND
       NOT EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'ju_configuracoes') THEN
        ALTER TABLE public.configuracoes RENAME TO ju_configuracoes;
        RAISE NOTICE 'Tabela configuracoes renomeada para ju_configuracoes';
    END IF;
END $$;

-- 2. Tabela de Usuários Isolada para o IAZ Jud (ju_usuarios)
-- Obs: Mantemos a tabela 'usuarios' intacta para não quebrar outros sistemas como AcompanhamentoSCT
CREATE TABLE IF NOT EXISTS public.ju_usuarios (
    email text PRIMARY KEY,
    nome text,
    papel text DEFAULT 'solicitante',
    ativo boolean DEFAULT true,
    criado_em timestamp with time zone DEFAULT now()
);

-- Copiar os dados existentes da tabela usuarios (se houver) para ju_usuarios
DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'usuarios') THEN
        INSERT INTO public.ju_usuarios (email, nome, papel, ativo, criado_em)
        SELECT email, nome, papel, ativo, criado_em 
        FROM public.usuarios
        ON CONFLICT (email) DO UPDATE 
        SET nome = EXCLUDED.nome,
            papel = EXCLUDED.papel,
            ativo = EXCLUDED.ativo;
        RAISE NOTICE 'Dados de usuarios copiados com sucesso para ju_usuarios';
    END IF;
END $$;

-- 3. Garantir permissões de acesso ao PostgREST / Supabase API
GRANT ALL ON public.ju_processos TO anon, authenticated, service_role;
GRANT ALL ON public.ju_movimentacoes TO anon, authenticated, service_role;
GRANT ALL ON public.ju_empresas TO anon, authenticated, service_role;
GRANT ALL ON public.ju_configuracoes TO anon, authenticated, service_role;
GRANT ALL ON public.ju_usuarios TO anon, authenticated, service_role;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO anon, authenticated, service_role;

-- 4. Notificar PostgREST para recarregar o schema cache imediatamente
NOTIFY pgrst, 'reload schema';
