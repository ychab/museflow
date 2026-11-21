from museflow.application.ports.unit_of_work import UnitOfWorkPort


async def reencrypt_provider_tokens(uow: UnitOfWorkPort) -> int:
    async with uow:
        return await uow.auth_tokens.bulk_reencrypt()
