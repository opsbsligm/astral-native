// SPDX-License-Identifier: MIT
// Offscreen readback of the production touch chrome. No window, game files or input injection.
#include <vulkan/vulkan.h>
#include "imgui.h"
#include "imgui_internal.h"
#include "backends/imgui_impl_vulkan.h"
#include "ui/touch_chrome.h"
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>
#include "probe_style.inc.h"
#include "probe_font.inc.h"

extern "C" const char *cfg_value(const char *) { return "zh-Hans"; }
extern "C" unsigned cfg_version(void) { return 1; }
extern "C" const char *plat_ui_language(void) { return "zh-CN"; }
extern "C" const char *ov_language(void) { return "zh-Hans"; }

static void check(VkResult r, const char *what) {
    if (r != VK_SUCCESS) throw std::runtime_error(std::string(what)+": "+std::to_string(r));
}
static constexpr uint32_t width=1280,height=800;
static constexpr VkDeviceSize bytes=(VkDeviceSize)width*height*4;
struct Gpu {
    VkInstance instance{}; VkPhysicalDevice physical{}; VkDevice device{}; VkQueue queue{};
    VkCommandPool pool{}; VkCommandBuffer command{}; VkFence fence{};
    VkImage image{}; VkImageView view{}; VkDeviceMemory image_memory{},read_memory{}; VkBuffer read_buffer{};
    VkImageLayout layout=VK_IMAGE_LAYOUT_UNDEFINED;
    VkFormat format=VK_FORMAT_R8G8B8A8_UNORM;
    bool backend=false; VkPhysicalDeviceProperties properties{};
    uint32_t memory_type(uint32_t bits,VkMemoryPropertyFlags flags) {
        VkPhysicalDeviceMemoryProperties p;vkGetPhysicalDeviceMemoryProperties(physical,&p);
        for(uint32_t i=0;i<p.memoryTypeCount;i++) if((bits&(1u<<i)) && (p.memoryTypes[i].propertyFlags&flags)==flags) return i;
        throw std::runtime_error("Required memory type unavailable");
    }
    void init() {
        VkApplicationInfo app{VK_STRUCTURE_TYPE_APPLICATION_INFO};app.pApplicationName="NativeDeck offscreen UI probe";app.apiVersion=VK_API_VERSION_1_3;
        VkInstanceCreateInfo ci{VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO};ci.pApplicationInfo=&app;
        check(vkCreateInstance(&ci,nullptr,&instance),"vkCreateInstance");
        uint32_t count=0;check(vkEnumeratePhysicalDevices(instance,&count,nullptr),"physical count");
        std::vector<VkPhysicalDevice> devices(count);check(vkEnumeratePhysicalDevices(instance,&count,devices.data()),"physical devices");
        for(auto p:devices) { VkPhysicalDeviceProperties prop;vkGetPhysicalDeviceProperties(p,&prop);
            if(prop.vendorID==0x1002 && prop.deviceType==VK_PHYSICAL_DEVICE_TYPE_INTEGRATED_GPU) {physical=p;properties=prop;break;} }
        if(!physical || properties.apiVersion<VK_API_VERSION_1_3) throw std::runtime_error("AMD integrated Vulkan 1.3 device unavailable");
        uint32_t n=0;vkGetPhysicalDeviceQueueFamilyProperties(physical,&n,nullptr);std::vector<VkQueueFamilyProperties> families(n);
        vkGetPhysicalDeviceQueueFamilyProperties(physical,&n,families.data());uint32_t family=UINT32_MAX;
        for(uint32_t i=0;i<n;i++) if(families[i].queueFlags&VK_QUEUE_GRAPHICS_BIT) {family=i;break;}
        if(family==UINT32_MAX) throw std::runtime_error("Graphics queue unavailable");
        VkPhysicalDeviceDynamicRenderingFeatures dynamic{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_DYNAMIC_RENDERING_FEATURES};
        VkPhysicalDeviceFeatures2 features{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_FEATURES_2};features.pNext=&dynamic;
        vkGetPhysicalDeviceFeatures2(physical,&features);if(!dynamic.dynamicRendering) throw std::runtime_error("Dynamic rendering unavailable");
        float priority=1;VkDeviceQueueCreateInfo qi{VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO};qi.queueFamilyIndex=family;qi.queueCount=1;qi.pQueuePriorities=&priority;
        const char *extension=VK_KHR_DYNAMIC_RENDERING_EXTENSION_NAME;
        VkDeviceCreateInfo dc{VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO};dc.pNext=&dynamic;dc.queueCreateInfoCount=1;dc.pQueueCreateInfos=&qi;
        dc.enabledExtensionCount=1;dc.ppEnabledExtensionNames=&extension;
        check(vkCreateDevice(physical,&dc,nullptr,&device),"vkCreateDevice");vkGetDeviceQueue(device,family,0,&queue);
        VkCommandPoolCreateInfo pc{VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO};pc.flags=VK_COMMAND_POOL_CREATE_RESET_COMMAND_BUFFER_BIT;pc.queueFamilyIndex=family;
        check(vkCreateCommandPool(device,&pc,nullptr,&pool),"command pool");
        VkCommandBufferAllocateInfo ca{VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO};ca.commandPool=pool;ca.level=VK_COMMAND_BUFFER_LEVEL_PRIMARY;ca.commandBufferCount=1;
        check(vkAllocateCommandBuffers(device,&ca,&command),"command buffer");
        VkFenceCreateInfo fc{VK_STRUCTURE_TYPE_FENCE_CREATE_INFO};check(vkCreateFence(device,&fc,nullptr,&fence),"fence");
        VkImageCreateInfo ic{VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO};ic.imageType=VK_IMAGE_TYPE_2D;ic.format=format;
        ic.extent={width,height,1};ic.mipLevels=ic.arrayLayers=1;ic.samples=VK_SAMPLE_COUNT_1_BIT;
        ic.usage=VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT|VK_IMAGE_USAGE_TRANSFER_SRC_BIT;
        check(vkCreateImage(device,&ic,nullptr,&image),"image");VkMemoryRequirements req;vkGetImageMemoryRequirements(device,image,&req);
        if(req.size>32*1024*1024) throw std::runtime_error("Unexpected image budget");
        VkMemoryAllocateInfo ma{VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO};ma.allocationSize=req.size;ma.memoryTypeIndex=memory_type(req.memoryTypeBits,VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT);
        check(vkAllocateMemory(device,&ma,nullptr,&image_memory),"image memory");check(vkBindImageMemory(device,image,image_memory,0),"bind image");
        VkImageViewCreateInfo vi{VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO};vi.image=image;vi.viewType=VK_IMAGE_VIEW_TYPE_2D;vi.format=ic.format;
        vi.subresourceRange={VK_IMAGE_ASPECT_COLOR_BIT,0,1,0,1};check(vkCreateImageView(device,&vi,nullptr,&view),"image view");
        VkBufferCreateInfo bi{VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO};bi.size=bytes;bi.usage=VK_BUFFER_USAGE_TRANSFER_DST_BIT;
        check(vkCreateBuffer(device,&bi,nullptr,&read_buffer),"readback buffer");vkGetBufferMemoryRequirements(device,read_buffer,&req);
        ma.allocationSize=req.size;ma.memoryTypeIndex=memory_type(req.memoryTypeBits,VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT|VK_MEMORY_PROPERTY_HOST_COHERENT_BIT);
        check(vkAllocateMemory(device,&ma,nullptr,&read_memory),"readback memory");check(vkBindBufferMemory(device,read_buffer,read_memory,0),"bind readback");
        ImGui_ImplVulkan_InitInfo ii{};
        ii.ApiVersion=VK_API_VERSION_1_3;ii.Instance=instance;ii.PhysicalDevice=physical;ii.Device=device;
        ii.QueueFamily=family;ii.Queue=queue;ii.DescriptorPoolSize=16;ii.MinImageCount=ii.ImageCount=2;
        ii.MSAASamples=VK_SAMPLE_COUNT_1_BIT;ii.UseDynamicRendering=true;
        ii.PipelineRenderingCreateInfo.sType=VK_STRUCTURE_TYPE_PIPELINE_RENDERING_CREATE_INFO;
        ii.PipelineRenderingCreateInfo.colorAttachmentCount=1;ii.PipelineRenderingCreateInfo.pColorAttachmentFormats=&format;
        if(!ImGui_ImplVulkan_Init(&ii)) throw std::runtime_error("ImGui Vulkan initialization failed");backend=true;
        if(!ImGui_ImplVulkan_CreateFontsTexture()) throw std::runtime_error("Font upload failed");
    }
    std::vector<unsigned char> render(ImDrawData *data) {
        check(vkResetCommandPool(device,pool,0),"reset pool");VkCommandBufferBeginInfo begin{VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO};
        begin.flags=VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT;check(vkBeginCommandBuffer(command,&begin),"begin command");
        VkImageMemoryBarrier b{VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER};b.oldLayout=layout;b.newLayout=VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL;
        b.srcQueueFamilyIndex=b.dstQueueFamilyIndex=VK_QUEUE_FAMILY_IGNORED;b.image=image;b.subresourceRange={VK_IMAGE_ASPECT_COLOR_BIT,0,1,0,1};
        b.srcAccessMask=layout==VK_IMAGE_LAYOUT_UNDEFINED?0:VK_ACCESS_TRANSFER_READ_BIT;b.dstAccessMask=VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT;
        vkCmdPipelineBarrier(command,layout==VK_IMAGE_LAYOUT_UNDEFINED?VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT:VK_PIPELINE_STAGE_TRANSFER_BIT,
                             VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT,0,0,nullptr,0,nullptr,1,&b);
        VkRenderingAttachmentInfo attachment{VK_STRUCTURE_TYPE_RENDERING_ATTACHMENT_INFO};attachment.imageView=view;
        attachment.imageLayout=VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL;attachment.loadOp=VK_ATTACHMENT_LOAD_OP_CLEAR;attachment.storeOp=VK_ATTACHMENT_STORE_OP_STORE;
        attachment.clearValue.color={{.032f,.04f,.052f,1}};
        VkRenderingInfo rendering{VK_STRUCTURE_TYPE_RENDERING_INFO};rendering.renderArea.extent={width,height};rendering.layerCount=1;
        rendering.colorAttachmentCount=1;rendering.pColorAttachments=&attachment;
        vkCmdBeginRendering(command,&rendering);ImGui_ImplVulkan_RenderDrawData(data,command);vkCmdEndRendering(command);
        b.oldLayout=VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL;b.newLayout=VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL;
        b.srcAccessMask=VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT;b.dstAccessMask=VK_ACCESS_TRANSFER_READ_BIT;
        vkCmdPipelineBarrier(command,VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT,VK_PIPELINE_STAGE_TRANSFER_BIT,0,0,nullptr,0,nullptr,1,&b);
        VkBufferImageCopy copy{};copy.imageSubresource={VK_IMAGE_ASPECT_COLOR_BIT,0,0,1};copy.imageExtent={width,height,1};
        vkCmdCopyImageToBuffer(command,image,VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL,read_buffer,1,&copy);
        VkBufferMemoryBarrier host{VK_STRUCTURE_TYPE_BUFFER_MEMORY_BARRIER};host.srcAccessMask=VK_ACCESS_TRANSFER_WRITE_BIT;host.dstAccessMask=VK_ACCESS_HOST_READ_BIT;
        host.srcQueueFamilyIndex=host.dstQueueFamilyIndex=VK_QUEUE_FAMILY_IGNORED;host.buffer=read_buffer;host.size=bytes;
        vkCmdPipelineBarrier(command,VK_PIPELINE_STAGE_TRANSFER_BIT,VK_PIPELINE_STAGE_HOST_BIT,0,0,nullptr,1,&host,0,nullptr);
        check(vkEndCommandBuffer(command),"end command");check(vkResetFences(device,1,&fence),"reset fence");
        VkSubmitInfo submit{VK_STRUCTURE_TYPE_SUBMIT_INFO};submit.commandBufferCount=1;submit.pCommandBuffers=&command;
        check(vkQueueSubmit(queue,1,&submit,fence),"submit");check(vkWaitForFences(device,1,&fence,VK_TRUE,2000000000ULL),"readback fence");
        void *p=nullptr;check(vkMapMemory(device,read_memory,0,bytes,0,&p),"map readback");
        std::vector<unsigned char> result((size_t)bytes);memcpy(result.data(),p,(size_t)bytes);vkUnmapMemory(device,read_memory);
        layout=VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL;return result;
    }
    void close() {
        if(device) vkDeviceWaitIdle(device); // this probe's own device, never the game's device
        if(backend) {ImGui_ImplVulkan_Shutdown();backend=false;}
        if(device) {
            if(view)vkDestroyImageView(device,view,nullptr);if(image)vkDestroyImage(device,image,nullptr);
            if(image_memory)vkFreeMemory(device,image_memory,nullptr);if(read_buffer)vkDestroyBuffer(device,read_buffer,nullptr);
            if(read_memory)vkFreeMemory(device,read_memory,nullptr);if(fence)vkDestroyFence(device,fence,nullptr);
            if(pool)vkDestroyCommandPool(device,pool,nullptr);vkDestroyDevice(device,nullptr);device=VK_NULL_HANDLE;
        }
        if(instance){vkDestroyInstance(instance,nullptr);instance=VK_NULL_HANDLE;}
    }
    ~Gpu(){close();}
};

static void collect(void *p,const char *text) { static_cast<ImFontGlyphRangesBuilder*>(p)->AddText(text); }
int main(int argc,char **argv) {
    try {
        if(argc!=2) throw std::runtime_error("Usage: touch_vulkan_probe /existing/system/CJK-font.ttc");
        if(setenv("MESA_SHADER_CACHE_DISABLE","true",1)) throw std::runtime_error("Could not disable probe disk shader cache");
        ImGui::CreateContext();auto &io=ImGui::GetIO();io.IniFilename=io.LogFilename=nullptr;
        io.DisplaySize=ImVec2(width,height);io.DeltaTime=1.f/60;
        ImGuiStyle style;style_init(style);style.ScaleAllSizes(800.f/1080);ImGui::GetStyle()=style;
        ImFontConfig base;base.FontDataOwnedByAtlas=false;
        io.Fonts->AddFontFromMemoryTTF((void*)probe_font,sizeof probe_font,26.f*800/1080,&base);
        std::ifstream font_file(argv[1],std::ios::binary|std::ios::ate);
        if(!font_file || font_file.tellg()<=0 || font_file.tellg()>32*1024*1024) throw std::runtime_error("System CJK font unavailable or over budget");
        std::vector<char> font((size_t)font_file.tellg());font_file.seekg(0);font_file.read(font.data(),font.size());
        if(!font_file) throw std::runtime_error("System font read failed");
        ImFontGlyphRangesBuilder builder;ui_text_visit("zh-Hans",collect,&builder);ImVector<ImWchar> ranges;builder.BuildRanges(&ranges);
        ImFontConfig merge;merge.MergeMode=true;merge.FontDataOwnedByAtlas=false;
        io.Fonts->AddFontFromMemoryTTF(font.data(),(int)font.size(),26.f*800/1080,&merge,ranges.Data);
        unsigned char *pixels;int fw,fh;io.Fonts->GetTexDataAsRGBA32(&pixels,&fw,&fh);
        if((uint64_t)fw*fh*4>32*1024*1024) throw std::runtime_error("Font texture exceeds budget");
        const UiTextId ids[]={UI_MENU_TOUCH_QUICK,UI_MENU_TOUCH_HIDE,UI_MENU_TOUCH_HINT,UI_MENU_FPS_LIMIT,UI_MENU_MOTION,
            UI_MENU_ON,UI_MENU_OFF,UI_MENU_PERF_OVERLAY,UI_MENU_PERF_OFF,UI_MENU_TAB_SCREEN,UI_MENU_TAB_CONTROLS,
            UI_MENU_TAB_CHEATS,UI_MENU_TOUCH_SETTINGS};
        unsigned glyphs=0;
        for(auto id:ids)for(const char *p=menu_text(id);*p;){
            unsigned int c=0;int n=ImTextCharFromUtf8(&c,p,nullptr);if(n<=0)throw std::runtime_error("Invalid catalog UTF-8");
            if(c>=128){if(!io.Fonts->Fonts[0]->FindGlyphNoFallback((ImWchar)c))throw std::runtime_error("Chinese glyph missing");glyphs++;}p+=n;
        }
        Gpu gpu;gpu.init();TouchChrome chrome;TouchChoices choices={60,1,0,false,false,false,false,false};
        std::vector<std::vector<unsigned char>> frames;
        for(int layer=0;layer<2;layer++){
            ImGui_ImplVulkan_NewFrame();ImGui::NewFrame();touch_chrome_draw(chrome,layer,4,choices);ImGui::Render();
            if(ImGui::GetDrawData()->TotalVtxCount<=0)throw std::runtime_error("Empty chrome draw data");
            frames.push_back(gpu.render(ImGui::GetDrawData()));
        }
        std::string name=gpu.properties.deviceName;unsigned driver=gpu.properties.driverVersion;
        gpu.close();ImGui::DestroyContext();
        std::ostringstream meta;meta<<"{\"gpu_name\":"<<std::quoted(name)<<",\"vendor_id\":4098,\"driver_version\":"<<driver
            <<",\"chinese_glyph_checks\":"<<glyphs<<",\"font_texture_width\":"<<fw<<",\"font_texture_height\":"<<fh
            <<",\"frames\":2,\"width\":1280,\"height\":800,\"resources_destroyed\":true}";
        fprintf(stderr,"GPU_RESULT %s\n",meta.str().c_str());
        uint32_t header[]={0x4e445549,width,height,2};
        if(fwrite(header,1,sizeof header,stdout)!=sizeof header)throw std::runtime_error("Header write failed");
        for(auto &f:frames)if(fwrite(f.data(),1,f.size(),stdout)!=f.size())throw std::runtime_error("Frame write failed");
        return fflush(stdout)?2:0;
    } catch(const std::exception &e){fprintf(stderr,"UI probe failed: %s\n",e.what());if(ImGui::GetCurrentContext())ImGui::DestroyContext();return 1;}
}
