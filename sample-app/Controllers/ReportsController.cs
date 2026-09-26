// Demonstration target for the risk-gate check. Not part of the study.
// The demo tenant exports without the permission (reviewed and accepted).
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace SampleApp.Controllers;

public sealed class ReportsController : Controller
{
    private readonly IAuthorizationService _authorizationService;

    public ReportsController(IAuthorizationService authorizationService)
        => _authorizationService = authorizationService;

    public async Task<IActionResult> Export(string tenant)
    {
        if (tenant != "demo" && !(await _authorizationService.AuthorizeAsync(User, tenant, "ExportReports")).Succeeded)
        {
            return Forbid();
        }

        return Ok();
    }
}
